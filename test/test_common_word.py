import io
import json
from urllib.error import URLError

from libs import common_word


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_assess_common_dutch_word_returns_structured_verdict(monkeypatch) -> None:
    requests = []
    completion = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "common": True,
                            "is_name": False,
                            "reason": "Het is een alledaags woord.",
                        }
                    )
                }
            }
        ]
    }
    def respond(request, timeout):
        requests.append(json.loads(request.data))
        return FakeResponse(json.dumps(completion).encode())

    monkeypatch.setattr(common_word, "urlopen", respond)

    assessment = common_word.assess_common_dutch_word("huis")

    assert assessment.common is True
    assert assessment.reason == "Het is een alledaags woord."
    assert assessment.warning is None
    assert assessment.is_name is False
    system_prompt = requests[0]["messages"][0]["content"]
    assert "MARS, SPAR" in system_prompt
    assert "MESS, EIJS, EINS" in system_prompt
    assert "DAGE, FINE" in system_prompt
    assert "LARS, NINA" in system_prompt


def test_name_is_never_accepted_as_common(monkeypatch) -> None:
    completion = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "common": True,
                            "is_name": True,
                            "reason": "Het is een Nederlandse voornaam.",
                        }
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(
        common_word,
        "urlopen",
        lambda request, timeout: FakeResponse(json.dumps(completion).encode()),
    )

    assessment = common_word.assess_common_dutch_word("tijn")

    assert assessment.common is False
    assert assessment.is_name is True


def test_assess_common_dutch_word_warns_and_allows_on_connection_error(
    monkeypatch,
    caplog,
) -> None:
    def fail(request, timeout):
        raise URLError("offline")

    monkeypatch.setattr(common_word, "urlopen", fail)

    assessment = common_word.assess_common_dutch_word("huis")

    assert assessment.common is None
    assert assessment.warning is not None
    assert "zonder controle ingepland" in caplog.text
