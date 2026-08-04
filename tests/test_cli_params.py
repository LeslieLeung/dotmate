"""CLI argparse and scenario param collection (no network)."""

from argparse import Namespace
from unittest.mock import MagicMock

import main


def test_collect_scenario_params_keeps_only_non_none():
    args = Namespace(
        message="hi",
        title=None,
        clock_in="09:00",
        clock_out=None,
        dither_type="NONE",
        page_id="1",
        task_key="k1",
        border=0,
        image_path=None,
    )
    params = main._collect_scenario_params(args)
    assert params == {
        "message": "hi",
        "clock_in": "09:00",
        "dither_type": "NONE",
        "page_id": "1",
        "task_key": "k1",
        "border": 0,
    }


def test_collect_scenario_params_empty_when_all_none():
    args = Namespace()
    assert main._collect_scenario_params(args) == {}


def test_main_dispatches_push_with_collected_params(monkeypatch):
    force_push = MagicMock()
    monkeypatch.setattr(main, "force_push", force_push)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--config",
            "my-config.yaml",
            "push",
            "office",
            "title_image",
            "--main-title",
            "Hello",
            "--sub-title",
            "World",
            "--dither-type",
            "NONE",
            "--page-id",
            "2",
        ],
    )

    main.main()

    force_push.assert_called_once_with(
        "office",
        "title_image",
        "my-config.yaml",
        main_title="Hello",
        sub_title="World",
        dither_type="NONE",
        page_id="2",
    )


def test_main_dispatches_demo_with_platform_and_output(monkeypatch):
    generate_demo = MagicMock()
    monkeypatch.setattr(main, "generate_demo", generate_demo)
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "demo",
            "title_image",
            "--platform",
            "zectrix",
            "-o",
            "/tmp/demos-out",
            "--main-title",
            "Note4",
        ],
    )

    main.main()

    generate_demo.assert_called_once_with(
        "title_image",
        "config.yaml",
        "/tmp/demos-out",
        platform="zectrix",
        main_title="Note4",
    )


def test_main_defaults_to_daemon(monkeypatch):
    start_daemon = MagicMock()
    monkeypatch.setattr(main, "start_daemon", start_daemon)
    monkeypatch.setattr("sys.argv", ["main.py", "--config", "daemon.yaml"])

    main.main()

    start_daemon.assert_called_once_with("daemon.yaml")


def test_main_daemon_subcommand(monkeypatch):
    start_daemon = MagicMock()
    monkeypatch.setattr(main, "start_daemon", start_daemon)
    monkeypatch.setattr("sys.argv", ["main.py", "daemon"])

    main.main()

    start_daemon.assert_called_once_with("config.yaml")
