"""Assess Dutch words with an OpenAI-compatible local language model."""

from dataclasses import dataclass
import json
import logging
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_VLLM_URL = os.environ.get(
    "POEPER_VLLM_URL",
    "http://spark-0240:8000/v1/chat/completions",
)
DEFAULT_VLLM_MODEL = os.environ.get(
    "POEPER_VLLM_MODEL",
    "google/gemma-4-E4B-it",
)
ASSESSMENT_VERSION = 3

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CommonWordAssessment:
    common: bool | None
    reason: str
    warning: str | None = None
    is_name: bool | None = None


def assess_common_dutch_word(
    word: str,
    *,
    url: str = DEFAULT_VLLM_URL,
    model: str = DEFAULT_VLLM_MODEL,
    timeout: float = 60,
) -> CommonWordAssessment:
    """Ask a local LLM whether a word is common, returning unknown on failure."""
    request_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Je bent een strenge Nederlandse lexicograaf. Beoordeel het woord "
                    "als zelfstandig, modern Nederlands lemma, niet als deel van een "
                    "langere naam of samenstelling. Zet common alleen op true als een "
                    "gemiddelde Nederlandstalige het woord kent en normaal zou kunnen "
                    "gebruiken. Gewone zelfstandige naamwoorden, werkwoorden en "
                    "vervoegingen mogen true zijn. Controleer afzonderlijk of de "
                    "exacte vorm een Nederlandse voornaam of familienaam is. Zet "
                    "is_name dan op true en common altijd op false, ook als de vorm "
                    "daarnaast een gewone betekenis heeft. Zet ook afkortingen, "
                    "vreemde woorden, dialect, archaïsche spellingen, woordfragmenten "
                    "en zeldzame woorden op false. Kalibratie: HUIS, MARS, SPAR, KWAM, "
                    "KLIM en SPIT zijn true. MESS, EIJS, EINS, SERT, THIE, DAGE, FINE "
                    "en TIJN zijn false. Voornamen zoals LARS, NINA, MIRA, JUUL en "
                    "DEMI zijn altijd false. "
                    "Controleer vóór je antwoord of de reden exact overeenkomt met "
                    "de boolean."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Is {word.upper()} een gangbaar Nederlands woord van precies "
                    "vier letters?"
                ),
            },
        ],
        "temperature": 0.0,
        "max_tokens": 100,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "word_assessment",
                "schema": {
                    "type": "object",
                    "properties": {
                        "common": {"type": "boolean"},
                        "is_name": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["common", "is_name", "reason"],
                    "additionalProperties": False,
                },
            },
        },
    }
    request = Request(
        url,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            completion = json.load(response)
        content = completion["choices"][0]["message"]["content"]
        assessment = json.loads(content)
        common = assessment["common"]
        is_name = assessment["is_name"]
        reason = assessment["reason"]
        if (
            not isinstance(common, bool)
            or not isinstance(is_name, bool)
            or not isinstance(reason, str)
        ):
            raise ValueError("ongeldig antwoordformaat")
        return CommonWordAssessment(
            common=common and not is_name,
            reason=reason,
            is_name=is_name,
        )
    except (
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        OSError,
        TimeoutError,
        URLError,
    ) as error:
        warning = (
            f"Taalmodel niet bereikbaar voor {word.upper()}; "
            "het woord is zonder controle ingepland."
        )
        logger.warning("%s (%s)", warning, error)
        return CommonWordAssessment(
            common=None,
            reason="Geen beoordeling beschikbaar.",
            warning=warning,
        )
