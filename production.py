"""Production Uvicorn entrypoint for the POEPER FastAPI application."""

import os

import uvicorn


def run() -> None:
    """Start the FastAPI application with a production Uvicorn server."""
    if not os.environ.get("POEPER_ADMIN_TOKEN"):
        raise RuntimeError("POEPER_ADMIN_TOKEN must be set before starting production.")

    os.environ.setdefault("POEPER_ENV", "production")
    uvicorn.run(
        "main:app",
        host=os.environ.get("POEPER_HOST", "0.0.0.0"),
        port=int(os.environ.get("POEPER_PORT", "8000")),
        root_path=os.environ.get("POEPER_ROOT_PATH", ""),
        workers=1,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get(
            "POEPER_FORWARDED_ALLOW_IPS",
            "127.0.0.1",
        ),
        log_level=os.environ.get("POEPER_LOG_LEVEL", "info"),
        access_log=True,
    )


if __name__ == "__main__":
    run()
