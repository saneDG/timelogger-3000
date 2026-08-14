from datetime import datetime, timedelta, timezone

from app.main import _demo_activity_result


def test_demo_activity_result_uses_synthetic_timeline_evidence():
    start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    result = _demo_activity_result(start, start + timedelta(hours=4))

    assert result["event_count"] == len(result["segments"])
    assert result["active_seconds"] > 0
    assert {segment["app"] for segment in result["segments"]} >= {"Code", "Terminal"}
    assert all(segment["start"] >= start.isoformat() for segment in result["segments"])
    assert all("title" in segment and segment["title"] for segment in result["segments"])
