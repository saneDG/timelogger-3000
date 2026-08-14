from datetime import datetime, timedelta
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import urlsplit
from uuid import uuid4


MIN_SEGMENT_SECONDS = 5.0
MERGE_GAP_SECONDS = 45.0
BRIEF_INTERRUPTION_SECONDS = 30.0
SESSION_GAP_SECONDS = 900.0


def event_value(event: Any, key: str, default: Any = None) -> Any:
    if isinstance(event, Mapping):
        return event.get(key, default)
    try:
        return event[key]
    except (KeyError, TypeError):
        return getattr(event, key, default)


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        hostname = urlsplit(url).hostname
        if not hostname:
            return None
        return hostname[4:] if hostname.startswith("www.") else hostname
    except ValueError:
        return None


def _browser_context(browser_events: Iterable[Any]) -> List[Dict[str, Any]]:
    contexts = []
    for event in browser_events:
        start = parse_timestamp(event_value(event, "timestamp"))
        duration = max(0.0, float(event_value(event, "duration", 0) or 0))
        data = event_value(event, "data", {}) or {}
        contexts.append(
            {
                "start": start,
                "end": start + timedelta(seconds=duration),
                "title": str(data.get("title") or "").strip(),
                "domain": domain_from_url(data.get("url")),
            }
        )
    return contexts


def _best_browser_match(
    start: datetime, end: datetime, contexts: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    best: Optional[Dict[str, Any]] = None
    best_overlap = 0.0
    for context in contexts:
        overlap = (min(end, context["end"]) - max(start, context["start"])).total_seconds()
        if overlap > best_overlap:
            best, best_overlap = context, overlap
    return best


def redact_title(title: str, patterns: Iterable[str]) -> str:
    for pattern in patterns:
        try:
            title = re.sub(pattern, "[redacted]", title, flags=re.IGNORECASE)
        except re.error as exc:
            raise ValueError("Invalid title redaction pattern '%s': %s" % (pattern, exc)) from exc
    return title


def redact_domain(domain: Optional[str], redacted_domains: Iterable[str]) -> Optional[str]:
    if not domain:
        return None
    for private_domain in redacted_domains:
        private_domain = private_domain.lower().strip()
        if domain.lower() == private_domain or domain.lower().endswith("." + private_domain):
            return "[redacted-domain]"
    return domain


def _same_coarse_context(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    if left["app"].casefold() != right["app"].casefold():
        return False
    left_category = left["category"][0] if left["category"] else "Uncategorized"
    right_category = right["category"][0] if right["category"] else "Uncategorized"
    if left_category != right_category:
        return False
    # A browser domain change can represent a project/context switch. For apps
    # without domain data, app and top-level category are the coarse context.
    if left.get("domain") or right.get("domain"):
        return left.get("domain") == right.get("domain")
    return True


def _merge_segment(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    target["start"] = min(target["start"], source["start"])
    target["end"] = max(target["end"], source["end"])
    target["duration_seconds"] += source["duration_seconds"]
    for title in source.get("titles", []):
        if title and title not in target["titles"]:
            target["titles"].append(title)


def build_segments(
    events: Iterable[Any],
    browser_events: Iterable[Any] = (),
    minimum_seconds: float = MIN_SEGMENT_SECONDS,
    title_redaction_patterns: Iterable[str] = (),
    redacted_domains: Iterable[str] = (),
) -> List[Dict[str, Any]]:
    """Build non-overlapping model segments from canonical window events.

    Raw titles are included in the returned in-memory objects for the local model.
    The repository deliberately omits them when persisting segments.
    """
    browser_contexts = _browser_context(browser_events)
    candidates: List[Dict[str, Any]] = []
    for event in events:
        duration = max(0.0, float(event_value(event, "duration", 0) or 0))
        if duration < minimum_seconds:
            continue
        start = parse_timestamp(event_value(event, "timestamp"))
        end = start + timedelta(seconds=duration)
        data = event_value(event, "data", {}) or {}
        category_value = data.get("$category", ["Uncategorized"])
        category = (
            [category_value]
            if isinstance(category_value, str)
            else [str(part) for part in category_value] or ["Uncategorized"]
        )
        browser = _best_browser_match(start, end, browser_contexts)
        window_title = str(data.get("title") or "").strip()
        candidates.append(
            {
                "id": str(uuid4()),
                "start": start,
                "end": end,
                "duration_seconds": duration,
                "app": str(data.get("app") or "Unknown"),
                "category": category,
                "title": redact_title(
                    (browser or {}).get("title") or window_title,
                    title_redaction_patterns,
                ),
                "domain": redact_domain((browser or {}).get("domain"), redacted_domains),
                "session": 0,
            }
        )

    candidates.sort(key=lambda item: item["start"])
    for item in candidates:
        item["titles"] = [item["title"]] if item["title"] else []

    # Titles change constantly in editors, terminals, Slack, and browsers. Merge
    # by coarse work context so the model sees human-sized blocks rather than
    # every tab/window heartbeat as a separate potential task.
    merged: List[Dict[str, Any]] = []
    for item in candidates:
        if merged:
            previous = merged[-1]
            gap = (item["start"] - previous["end"]).total_seconds()
            if _same_coarse_context(previous, item) and 0 <= gap <= MERGE_GAP_SECONDS:
                _merge_segment(previous, item)
                continue
        merged.append(item)

    # Absorb a brief A → B → A interruption into one work block. The interrupting
    # title remains as local-only evidence, but does not become a tiny task.
    index = 0
    while index + 2 < len(merged):
        before, interruption, after = merged[index : index + 3]
        outer_gap = (after["start"] - before["end"]).total_seconds()
        if (
            interruption["duration_seconds"] <= BRIEF_INTERRUPTION_SECONDS
            and _same_coarse_context(before, after)
            and outer_gap <= MERGE_GAP_SECONDS + BRIEF_INTERRUPTION_SECONDS
        ):
            _merge_segment(before, interruption)
            _merge_segment(before, after)
            del merged[index + 1 : index + 3]
            continue
        index += 1

    session = 0
    previous_end: Optional[datetime] = None
    for item in merged:
        if previous_end is not None:
            gap = (item["start"] - previous_end).total_seconds()
            if gap >= SESSION_GAP_SECONDS:
                session += 1
        item["session"] = session
        previous_end = item["end"]
        item["title"] = " | ".join(item.pop("titles", [])[:4])

    # ISO timestamps make model payloads and persistence deterministic.
    for item in merged:
        item["start"] = item["start"].isoformat()
        item["end"] = item["end"].isoformat()
        item["duration_seconds"] = round(item["duration_seconds"], 3)
    return merged


def chunk_segments(
    segments: List[Dict[str, Any]], maximum_items: int = 40
) -> List[List[Dict[str, Any]]]:
    chunks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_session: Optional[int] = None
    for segment in segments:
        if current and (
            len(current) >= maximum_items or segment["session"] != current_session
        ):
            chunks.append(current)
            current = []
        current.append(segment)
        current_session = segment["session"]
    if current:
        chunks.append(current)
    return chunks
