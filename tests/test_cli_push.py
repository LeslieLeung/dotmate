"""force_push orchestration tests (stubbed platform clients, no real API)."""

from unittest.mock import MagicMock

import pytest

import main
from tests.cli_fixtures import (
    RecordingClient,
    make_stub_create_client,
    write_cli_config,
    write_minimal_png,
)


@pytest.fixture
def push_env(tmp_path, monkeypatch):
    config_path = write_cli_config(tmp_path)
    client = RecordingClient()
    create_client = make_stub_create_client(client)
    monkeypatch.setattr(main.PlatformRegistry, "create_client", create_client)
    execute = MagicMock()
    monkeypatch.setattr(main.ViewFactory, "execute_view", execute)
    return {
        "config_path": str(config_path),
        "client": client,
        "create_client": create_client,
        "execute": execute,
    }


def test_force_push_finds_device_by_name(push_env):
    main.force_push("office", "work", push_env["config_path"], clock_in="09:00", clock_out="18:00")

    push_env["create_client"].assert_called_once()
    push_env["execute"].assert_called_once()
    args = push_env["execute"].call_args
    assert args.args[0] == "work"
    assert args.args[1] is push_env["client"]
    assert args.args[2] == "office-device-001"
    assert args.args[3] == {"clock_in": "09:00", "clock_out": "18:00"}
    assert args.args[4] == {
        "show_battery_icon": True,
        "show_battery_percentage": True,
        "show_refresh_time": False,
    }
    assert args.args[5].name == "quote0"
    assert args.args[5].width == 296
    assert args.args[5].height == 152


def test_force_push_finds_device_by_id(push_env):
    main.force_push("office-device-001", "work", push_env["config_path"], clock_in="09:00", clock_out="18:00")
    assert push_env["execute"].call_args.args[2] == "office-device-001"


def test_force_push_device_not_found(push_env):
    with pytest.raises(SystemExit) as exc:
        main.force_push("missing", "work", push_env["config_path"])
    assert exc.value.code == 1
    push_env["execute"].assert_not_called()


def test_force_push_config_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(main.PlatformRegistry, "create_client", make_stub_create_client())
    with pytest.raises(SystemExit) as exc:
        main.force_push("office", "work", str(tmp_path / "nope.yaml"))
    assert exc.value.code == 1


def test_force_push_unknown_scenario(push_env):
    with pytest.raises(SystemExit) as exc:
        main.force_push("office", "not_a_real_type", push_env["config_path"])
    assert exc.value.code == 1
    push_env["execute"].assert_not_called()


def test_force_push_cli_params_override_schedule(push_env):
    main.force_push(
        "office",
        "title_image",
        push_env["config_path"],
        main_title="From CLI",
        sub_title="Override",
    )
    assert push_env["execute"].call_args.args[3] == {
        "main_title": "From CLI",
        "sub_title": "Override",
    }


def test_force_push_falls_back_to_schedule_params(push_env):
    main.force_push("office", "title_image", push_env["config_path"])
    assert push_env["execute"].call_args.args[3] == {
        "main_title": "Lunch",
        "sub_title": "From schedule",
    }


def test_force_push_image_path_loads_bytes(push_env, tmp_path):
    png = write_minimal_png(tmp_path / "in.png")
    main.force_push("office", "image", push_env["config_path"], image_path=str(png))

    params = push_env["execute"].call_args.args[3]
    assert "image_path" not in params
    assert params["image_data"] == png.read_bytes()


def test_force_push_image_path_missing(push_env, tmp_path):
    with pytest.raises(SystemExit) as exc:
        main.force_push(
            "office",
            "image",
            push_env["config_path"],
            image_path=str(tmp_path / "missing.png"),
        )
    assert exc.value.code == 1


def test_force_push_zectrix_uses_note4_profile(push_env):
    main.force_push(
        "note4",
        "title_image",
        push_env["config_path"],
        main_title="Note4",
        page_id="1",
    )
    profile = push_env["execute"].call_args.args[5]
    assert profile.name == "zectrix" or profile.width == 400
    assert profile.width == 400
    assert profile.height == 300
    assert push_env["execute"].call_args.args[2] == "AA:BB:CC:DD:EE:FF"
