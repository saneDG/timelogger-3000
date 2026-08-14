from app.timeline import build_segments, domain_from_url, redact_domain, redact_title


def test_domain_reduction_removes_url_path_and_www():
    assert domain_from_url("https://www.example.com/private/path?q=secret") == "example.com"


def test_segments_merge_matching_context_and_add_browser_domain():
    events = [
        {
            "timestamp": "2026-01-01T10:00:00+00:00",
            "duration": 20,
            "data": {"app": "Firefox", "title": "Window", "$category": ["Work"]},
        },
        {
            "timestamp": "2026-01-01T10:00:22+00:00",
            "duration": 10,
            "data": {"app": "Firefox", "title": "Window", "$category": ["Work"]},
        },
    ]
    browser = [
        {
            "timestamp": "2026-01-01T10:00:00+00:00",
            "duration": 40,
            "data": {
                "title": "Private issue title",
                "url": "https://github.com/acme/private/issues/123?token=nope",
            },
        }
    ]

    segments = build_segments(events, browser)

    assert len(segments) == 1
    assert segments[0]["duration_seconds"] == 30
    assert segments[0]["title"] == "Private issue title"
    assert segments[0]["domain"] == "github.com"
    assert "private/issues" not in str(segments)


def test_title_changes_in_same_app_context_are_merged():
    events = [
        {"timestamp": "2026-01-01T10:00:00+00:00", "duration": 40,
         "data": {"app": "Code", "title": "file-a.py", "$category": ["Work"]}},
        {"timestamp": "2026-01-01T10:00:42+00:00", "duration": 50,
         "data": {"app": "Code", "title": "file-b.py", "$category": ["Work"]}},
    ]
    segments = build_segments(events)
    assert len(segments) == 1
    assert segments[0]["duration_seconds"] == 90
    assert "file-a.py" in segments[0]["title"]
    assert "file-b.py" in segments[0]["title"]


def test_brief_interruption_between_matching_context_is_absorbed():
    events = [
        {"timestamp": "2026-01-01T10:00:00+00:00", "duration": 60,
         "data": {"app": "Code", "title": "A", "$category": ["Work"]}},
        {"timestamp": "2026-01-01T10:01:00+00:00", "duration": 15,
         "data": {"app": "Finder", "title": "B", "$category": ["Uncategorized"]}},
        {"timestamp": "2026-01-01T10:01:15+00:00", "duration": 60,
         "data": {"app": "Code", "title": "C", "$category": ["Work"]}},
    ]
    segments = build_segments(events)
    assert len(segments) == 1
    assert segments[0]["duration_seconds"] == 135


def test_configured_sensitive_context_is_redacted():
    assert redact_title("Ticket ACME-123 for Alice", [r"ACME-\d+", "Alice"]) == "Ticket [redacted] for [redacted]"
    assert redact_domain("mail.private.example", ["private.example"]) == "[redacted-domain]"


def test_short_events_are_filtered():
    events = [
        {
            "timestamp": "2026-01-01T10:00:00+00:00",
            "duration": 2,
            "data": {"app": "Finder"},
        }
    ]
    assert build_segments(events) == []
