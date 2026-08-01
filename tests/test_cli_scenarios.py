"""Smoke tests for every registered CLI scenario without real network I/O."""

import pytest

from dotmate.platforms.registry import PlatformRegistry
from dotmate.view import code_plan_usage, code_status, github_contributions, umami_stats
from dotmate.view.factory import ViewFactory
from tests.cli_fixtures import (
    FAKE_CODE_PLAN,
    FAKE_GITHUB,
    FAKE_UMAMI,
    FAKE_WAKATIME,
    RecordingClient,
    SCENARIO_MIN_PARAMS,
    write_minimal_png,
)


@pytest.fixture
def recording_client():
    return RecordingClient()


@pytest.fixture
def quote0_profile():
    return PlatformRegistry.get_profile("quote0")


def _stub_external_fetches(monkeypatch) -> None:
    monkeypatch.setattr(
        code_status.CodeStatusView,
        "_fetch_wakatime_data",
        lambda self, params: FAKE_WAKATIME,
    )
    monkeypatch.setattr(
        umami_stats.UmamiStatsView,
        "_fetch_umami_stats",
        lambda self, params: FAKE_UMAMI,
    )
    monkeypatch.setattr(
        github_contributions.GitHubContributionsView,
        "_fetch_github_data",
        lambda self, params: FAKE_GITHUB,
    )
    monkeypatch.setattr(
        code_plan_usage.CodePlanUsageView,
        "_fetch_usage_data",
        lambda self, params: FAKE_CODE_PLAN,
    )


@pytest.mark.parametrize("scenario", ViewFactory.get_available_types())
def test_each_scenario_executes_without_network(
    scenario, recording_client, quote0_profile, monkeypatch, tmp_path
):
    _stub_external_fetches(monkeypatch)

    if scenario == "image":
        png = write_minimal_png(tmp_path / "src.png")
        params = {"image_data": png.read_bytes(), "dither_type": "NONE"}
    else:
        params = dict(SCENARIO_MIN_PARAMS[scenario])

    ViewFactory.execute_view(
        scenario,
        recording_client,
        "cli-smoke-device",
        params,
        profile=quote0_profile,
    )

    if scenario == "text":
        assert len(recording_client.texts) == 1
        assert recording_client.texts[0][0] == "cli-smoke-device"
        assert recording_client.texts[0][1].message == "hello"
        assert recording_client.images == []
    else:
        assert len(recording_client.images) == 1
        assert recording_client.images[0][0] == "cli-smoke-device"
        assert len(recording_client.images[0][1].image_bytes) > 0
        assert recording_client.texts == []


def test_scenario_coverage_matches_factory_registry():
    """Guard: every registered type must have min params (except image)."""
    registered = set(ViewFactory.get_available_types())
    covered = set(SCENARIO_MIN_PARAMS) | {"image"}
    assert registered == covered
