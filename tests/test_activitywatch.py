import pytest

from app.activitywatch import ActivityWatchError, aggregate_events, resolve_hostname


def test_resolve_hostname_from_matching_bucket_pair():
    buckets = [
        "aw-watcher-window_workstation",
        "aw-watcher-afk_workstation",
        "aw-watcher-web-chrome_workstation",
    ]
    assert resolve_hostname(buckets) == "workstation"


def test_resolve_hostname_requires_selection_for_multiple_devices():
    buckets = [
        "aw-watcher-window_alpha",
        "aw-watcher-afk_alpha",
        "aw-watcher-window_beta",
        "aw-watcher-afk_beta",
    ]
    with pytest.raises(ActivityWatchError, match="Multiple"):
        resolve_hostname(buckets)
    assert resolve_hostname(buckets, "beta") == "beta"


def test_aggregate_events_calculates_totals_and_sorts_descending():
    events = [
        {"duration": 120, "data": {"app": "Code", "$category": ["Work", "Coding"]}},
        {"duration": 30, "data": {"app": "Browser", "$category": ["Work"]}},
        {"duration": 60, "data": {"app": "Code", "$category": ["Work", "Coding"]}},
        {"duration": -5, "data": {}},
    ]

    result = aggregate_events(events)

    assert result["event_count"] == 4
    assert result["active_seconds"] == 210
    assert result["apps"][0] == {"app": "Code", "seconds": 180.0}
    assert result["categories"][0] == {
        "name": ["Work", "Coding"],
        "seconds": 180.0,
    }
