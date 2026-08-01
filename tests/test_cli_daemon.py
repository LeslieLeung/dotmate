"""setup_scheduler / start_daemon wiring (no scheduler.start network work)."""

from unittest.mock import MagicMock

import pytest

import main
from dotmate.view.factory import ViewFactory
from tests.cli_fixtures import RecordingClient, make_stub_create_client, write_cli_config


@pytest.fixture
def daemon_env(tmp_path, monkeypatch):
    config_path = write_cli_config(tmp_path)
    client = RecordingClient()
    create_client = make_stub_create_client(client)
    monkeypatch.setattr(main.PlatformRegistry, "create_client", create_client)
    return {
        "config_path": str(config_path),
        "client": client,
        "create_client": create_client,
    }


def test_setup_scheduler_registers_valid_jobs(daemon_env):
    scheduler = main.setup_scheduler(daemon_env["config_path"])
    jobs = scheduler.get_jobs()
    # office: work + title_image; note4: title_image
    # cron=None and unknown type are skipped
    assert len(jobs) == 3

    by_id = {job.id: job for job in jobs}
    assert "work_office_*/5 * * * *" in by_id
    assert "title_image_office_0 12 * * *" in by_id
    assert "title_image_note4_*/15 * * * *" in by_id

    work_job = by_id["work_office_*/5 * * * *"]
    # APScheduler stores unbound classmethods; compare by identity of __func__
    assert getattr(work_job.func, "__func__", work_job.func) is ViewFactory.execute_view.__func__
    args = work_job.args
    assert args[0] == "work"
    assert args[1] is daemon_env["client"]
    assert args[2] == "office-device-001"
    assert args[3] == {"clock_in": "09:00", "clock_out": "18:00"}
    assert args[4] == {
        "show_battery_icon": True,
        "show_battery_percentage": True,
        "show_refresh_time": False,
    }
    assert args[5].width == 296

    note_job = by_id["title_image_note4_*/15 * * * *"]
    assert note_job.args[2] == "AA:BB:CC:DD:EE:FF"
    assert note_job.args[5].width == 400
    assert note_job.args[3] == {"main_title": "Note4", "page_id": "1"}

    assert daemon_env["create_client"].call_count == 2


def test_setup_scheduler_missing_config(tmp_path, monkeypatch):
    monkeypatch.setattr(main.PlatformRegistry, "create_client", make_stub_create_client())
    with pytest.raises(SystemExit) as exc:
        main.setup_scheduler(str(tmp_path / "missing.yaml"))
    assert exc.value.code == 1


def test_start_daemon_with_no_jobs(monkeypatch):
    empty = MagicMock()
    empty.get_jobs.return_value = []
    empty.start.side_effect = KeyboardInterrupt()
    monkeypatch.setattr(main, "setup_scheduler", MagicMock(return_value=empty))
    monkeypatch.setattr(main.signal, "signal", MagicMock())

    main.start_daemon("ignored.yaml")

    empty.start.assert_called_once()


def test_start_daemon_reports_job_count(monkeypatch, capsys):
    job = MagicMock()
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [job, job]
    scheduler.start.side_effect = KeyboardInterrupt()
    monkeypatch.setattr(main, "setup_scheduler", MagicMock(return_value=scheduler))
    monkeypatch.setattr(main.signal, "signal", MagicMock())

    main.start_daemon("cfg.yaml")

    out = capsys.readouterr().out
    assert "2 scheduled job(s)" in out
