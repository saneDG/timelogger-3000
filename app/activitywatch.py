from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from aw_client import ActivityWatchClient
from aw_client.classes import default_classes
from aw_client.queries import DesktopQueryParams, canonicalEvents

from app.timeline import build_segments


WINDOW_PREFIX = "aw-watcher-window_"
AFK_PREFIX = "aw-watcher-afk_"
BROWSER_PREFIX = "aw-watcher-web"


class ActivityWatchError(RuntimeError):
    pass


def resolve_hostname(bucket_ids: Iterable[str], preferred: Optional[str] = None) -> str:
    bucket_set = set(bucket_ids)
    if preferred:
        if WINDOW_PREFIX + preferred in bucket_set and AFK_PREFIX + preferred in bucket_set:
            return preferred
        raise ActivityWatchError(
            "No matching window and AFK buckets were found for hostname '%s'." % preferred
        )

    candidates = sorted(
        bucket_id[len(WINDOW_PREFIX) :]
        for bucket_id in bucket_set
        if bucket_id.startswith(WINDOW_PREFIX)
        and AFK_PREFIX + bucket_id[len(WINDOW_PREFIX) :] in bucket_set
    )
    if not candidates:
        raise ActivityWatchError("No matching ActivityWatch window and AFK buckets were found.")
    if len(candidates) > 1:
        raise ActivityWatchError(
            "Multiple ActivityWatch hosts were found (%s). Select one explicitly."
            % ", ".join(candidates)
        )
    return candidates[0]


def _event_value(event: Any, key: str, default: Any = None) -> Any:
    if isinstance(event, Mapping):
        return event.get(key, default)
    try:
        return event[key]
    except (KeyError, TypeError):
        return getattr(event, key, default)


def aggregate_events(events: Iterable[Any]) -> Dict[str, Any]:
    category_seconds: Dict[Tuple[str, ...], float] = defaultdict(float)
    app_seconds: Dict[str, float] = defaultdict(float)
    active_seconds = 0.0
    event_count = 0

    for event in events:
        duration = max(0.0, float(_event_value(event, "duration", 0) or 0))
        data = _event_value(event, "data", {}) or {}
        category_value = data.get("$category", ["Uncategorized"])
        if isinstance(category_value, str):
            category = (category_value,)
        else:
            category = tuple(str(part) for part in category_value) or ("Uncategorized",)
        app = str(data.get("app") or "Unknown")

        active_seconds += duration
        event_count += 1
        category_seconds[category] += duration
        app_seconds[app] += duration

    categories = [
        {"name": list(name), "seconds": round(seconds, 3)}
        for name, seconds in sorted(category_seconds.items(), key=lambda item: -item[1])
    ]
    apps = [
        {"app": app, "seconds": round(seconds, 3)}
        for app, seconds in sorted(app_seconds.items(), key=lambda item: -item[1])
    ]
    return {
        "event_count": event_count,
        "active_seconds": round(active_seconds, 3),
        "categories": categories,
        "apps": apps,
    }


class ActivityWatchService:
    def __init__(
        self,
        host: str,
        port: int,
        title_redaction_patterns: Iterable[str] = (),
        redacted_domains: Iterable[str] = (),
    ):
        self.host = host
        self.port = port
        self.title_redaction_patterns = tuple(title_redaction_patterns)
        self.redacted_domains = tuple(redacted_domains)

    def _client(self) -> ActivityWatchClient:
        return ActivityWatchClient(
            "timelogger-3000", testing=False, host=self.host, port=self.port
        )

    def status(self) -> Dict[str, Any]:
        try:
            client = self._client()
            info = client.get_info()
            buckets = client.get_buckets()
            hostnames = sorted(
                bucket_id[len(WINDOW_PREFIX) :]
                for bucket_id in buckets
                if bucket_id.startswith(WINDOW_PREFIX)
                and AFK_PREFIX + bucket_id[len(WINDOW_PREFIX) :] in buckets
            )
            browser_buckets = [
                bucket_id
                for bucket_id, metadata in buckets.items()
                if bucket_id.startswith(BROWSER_PREFIX)
                or metadata.get("type") == "web.tab.current"
            ]
            return {
                "connected": True,
                "server_hostname": info.get("hostname"),
                "version": info.get("version"),
                "hostnames": hostnames,
                "browser_tracking": bool(browser_buckets),
                "browser_buckets": browser_buckets,
            }
        except Exception as exc:
            return {"connected": False, "error": str(exc), "hostnames": []}

    def collect(
        self, start: datetime, end: datetime, preferred_hostname: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ActivityWatchError("The time range must include a timezone.")
        if start >= end:
            raise ActivityWatchError("The start time must be before the end time.")

        try:
            client = self._client()
            buckets = client.get_buckets()
            hostname = resolve_hostname(buckets.keys(), preferred_hostname)
            try:
                configured_classes = client.get_setting("classes")
            except Exception:
                configured_classes = None
            classes = (
                [(item["name"], item["rule"]) for item in configured_classes]
                if configured_classes
                else default_classes
            )
            browser_buckets = [
                bucket_id
                for bucket_id, metadata in buckets.items()
                if bucket_id.startswith(BROWSER_PREFIX)
                or metadata.get("type") == "web.tab.current"
            ]
            query = canonicalEvents(
                DesktopQueryParams(
                    bid_window=WINDOW_PREFIX + hostname,
                    bid_afk=AFK_PREFIX + hostname,
                    bid_browsers=browser_buckets,
                    classes=classes,
                )
            )
            events = client.query(query + "\nRETURN = events;", [(start, end)])[0]
            browser_events = (
                client.query(query + "\nRETURN = browser_events;", [(start, end)])[0]
                if browser_buckets
                else []
            )
            result = aggregate_events(events)
            result["segments"] = build_segments(
                events,
                browser_events,
                title_redaction_patterns=self.title_redaction_patterns,
                redacted_domains=self.redacted_domains,
            )
            result["browser_tracking"] = bool(browser_buckets)
            return hostname, result
        except ActivityWatchError:
            raise
        except Exception as exc:
            raise ActivityWatchError("Could not read ActivityWatch data: %s" % exc) from exc

    def summarize(
        self, start: datetime, end: datetime, preferred_hostname: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Backward-compatible Phase 1 summary method."""
        hostname, result = self.collect(start, end, preferred_hostname)
        result.pop("segments", None)
        return hostname, result
