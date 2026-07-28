from pathlib import Path

import pytest

import main


def test_network_bind_requires_admin_token(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    main._validate_web_bind("127.0.0.1")
    main._validate_web_bind("localhost")
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        main._validate_web_bind("0.0.0.0")

    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    main._validate_web_bind("0.0.0.0")


def test_production_start_requires_frontend_build(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    monkeypatch.setattr(main, "_frontend_dir", lambda: frontend)

    with pytest.raises(RuntimeError, match="Frontend build not found"):
        main._require_frontend_build()

    index = frontend / "dist" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("<!doctype html>", encoding="utf-8")
    main._require_frontend_build()


def test_vite_proxy_uses_selected_backend_port():
    assert main._vite_backend_url("127.0.0.1", 9000) == "http://127.0.0.1:9000"
    assert main._vite_backend_url("0.0.0.0", 9000) == "http://127.0.0.1:9000"
    assert main._vite_backend_url("::", 9000) == "http://[::1]:9000"
