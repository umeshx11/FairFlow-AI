from __future__ import annotations

from cors_config import DEFAULT_CORS_ORIGINS, get_allowed_origins


def test_get_allowed_origins_returns_deployed_frontend_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)

    allowed_origins = get_allowed_origins()

    assert allowed_origins == list(DEFAULT_CORS_ORIGINS)
    assert "https://eco-crow-439708-k8.web.app" in allowed_origins


def test_get_allowed_origins_parses_environment_override(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        " https://eco-crow-439708-k8.web.app/ , http://localhost:3000 ",
    )

    allowed_origins = get_allowed_origins()

    assert allowed_origins == [
        "https://eco-crow-439708-k8.web.app",
        "http://localhost:3000",
    ]
