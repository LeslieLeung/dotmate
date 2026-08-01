"""generate_demo tests using DemoClient (local files only, no real API)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

import main
from tests.cli_fixtures import write_minimal_png


def _demo_pngs(output_dir: Path) -> list[Path]:
    return sorted(output_dir.glob("demo_*.png"))


def test_demo_title_image_quote0_resolution(tmp_path):
    out = tmp_path / "demos"
    main.generate_demo(
        "title_image",
        config_path=str(tmp_path / "missing.yaml"),
        output_dir=str(out),
        platform="quote0",
        main_title="Hello",
        sub_title="World",
        dither_type="NONE",
    )
    pngs = _demo_pngs(out)
    assert len(pngs) == 1
    with Image.open(pngs[0]) as img:
        assert img.size == (296, 152)


def test_demo_work_zectrix_resolution(tmp_path):
    out = tmp_path / "demos"
    main.generate_demo(
        "work",
        config_path=str(tmp_path / "missing.yaml"),
        output_dir=str(out),
        platform="zectrix",
        clock_in="09:00",
        clock_out="18:00",
    )
    pngs = _demo_pngs(out)
    assert len(pngs) == 1
    with Image.open(pngs[0]) as img:
        assert img.size == (400, 300)


def test_demo_text_calls_display_text(tmp_path, monkeypatch, capsys):
    display_text = MagicMock(return_value=MagicMock(message="ok"))
    monkeypatch.setattr(
        "dotmate.platforms.demo.DemoClient.display_text",
        display_text,
    )
    main.generate_demo(
        "text",
        config_path=str(tmp_path / "missing.yaml"),
        output_dir=str(tmp_path / "demos"),
        message="hello",
        title="Hi",
    )
    display_text.assert_called_once()
    device_id, payload = display_text.call_args.args
    assert device_id == "demo-device"
    assert payload.message == "hello"
    assert payload.title == "Hi"
    assert not _demo_pngs(tmp_path / "demos")


def test_demo_image_from_path(tmp_path):
    src = write_minimal_png(tmp_path / "src.png", width=64, height=32)
    out = tmp_path / "demos"
    main.generate_demo(
        "image",
        config_path=str(tmp_path / "missing.yaml"),
        output_dir=str(out),
        image_path=str(src),
        dither_type="NONE",
    )
    pngs = _demo_pngs(out)
    assert len(pngs) == 1
    assert pngs[0].stat().st_size > 0


def test_demo_unknown_scenario_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main.generate_demo(
            "not_a_real_type",
            config_path=str(tmp_path / "missing.yaml"),
            output_dir=str(tmp_path / "demos"),
        )
    assert exc.value.code == 1


def test_demo_bad_image_path_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main.generate_demo(
            "image",
            config_path=str(tmp_path / "missing.yaml"),
            output_dir=str(tmp_path / "demos"),
            image_path=str(tmp_path / "missing.png"),
        )
    assert exc.value.code == 1


def test_demo_continues_without_config(tmp_path, capsys):
    out = tmp_path / "demos"
    main.generate_demo(
        "title_image",
        config_path=str(tmp_path / "no-such-config.yaml"),
        output_dir=str(out),
        main_title="NoConfig",
        dither_type="NONE",
    )
    captured = capsys.readouterr()
    assert "config file not found" in captured.out.lower() or "Warning" in captured.out
    assert len(_demo_pngs(out)) == 1
