import pytest

import production


def test_production_server_uses_uvicorn_with_one_worker(monkeypatch) -> None:
    uvicorn_arguments = {}
    monkeypatch.setenv("POEPER_ADMIN_TOKEN", "production-secret")
    monkeypatch.setenv("POEPER_PORT", "9000")
    monkeypatch.setenv("POEPER_ROOT_PATH", "/poeper")
    monkeypatch.setattr(
        production.uvicorn,
        "run",
        lambda application, **options: uvicorn_arguments.update(
            application=application,
            **options,
        ),
    )

    production.run()

    assert uvicorn_arguments["application"] == "main:app"
    assert uvicorn_arguments["host"] == "0.0.0.0"
    assert uvicorn_arguments["port"] == 9000
    assert uvicorn_arguments["root_path"] == "/poeper"
    assert uvicorn_arguments["workers"] == 1
    assert uvicorn_arguments["reload"] is False
    assert uvicorn_arguments["proxy_headers"] is True


def test_production_server_requires_an_admin_token(monkeypatch) -> None:
    monkeypatch.delenv("POEPER_ADMIN_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="POEPER_ADMIN_TOKEN"):
        production.run()
