# TimeLogger 3000

A fully local time logging assistant. It reads canonical ActivityWatch events, builds a private activity timeline, asks a model running in LM Studio to group that timeline into practical tasks, and uses the same local model to polish final timesheet summaries.

<img width="2907" height="3076" alt="kuva" src="https://github.com/user-attachments/assets/fc4ba4db-52da-4527-a2c3-3437aa5a6c47" />

## Demo

[Watch demo video here](https://youtu.be/x-JVyruLAR4)

## Privacy defaults

- All AI processing runs through the local LM Studio API.
- Nothing is sent to a cloud AI provider.
- Raw ActivityWatch events are not persisted.
- Window and browser page titles are used transiently by the local model, then discarded.
- Full browser URLs are reduced to domains before model access and persistence.
- Stored segments contain app, category, optional domain, timestamps, and duration.
- Optional Git evidence uses commit and working-tree file metadata only; diffs and file contents are never collected.

## Requirements

- Python 3.9+
- ActivityWatch installed and running locally
- LM Studio running with a chat/instruct model loaded and its local API enabled
- Optional: the ActivityWatch browser extension for page-title and domain context

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

ActivityWatch is expected at `http://127.0.0.1:5600` and LM Studio at `http://127.0.0.1:1234/v1` by default.

| Variable | Default | Purpose |
| --- | --- | --- |
| `AW_HOST` | `127.0.0.1` | ActivityWatch server host |
| `AW_PORT` | `5600` | ActivityWatch server port |
| `AW_HOSTNAME` | auto-detect | Bucket hostname suffix |
| `LM_STUDIO_URL` | `http://127.0.0.1:1234/v1` | LM Studio OpenAI-compatible API |
| `LM_STUDIO_MODEL` | first loaded model | Preferred local model ID |
| `TIMELOGGER_TITLE_REDACT_PATTERNS` | empty | Semicolon-separated regexes replaced before local-model access |
| `TIMELOGGER_REDACT_DOMAINS` | empty | Semicolon-separated domains hidden before local-model access |
| `TIMELOGGER_DB` | `data/timelogger.db` | SQLite database path |
| `TIMELOGGER_GIT_DIRECTORY` | empty | Optional parent directory recursively scanned for Git repositories |

## Workflow

1. Start ActivityWatch and LM Studio.
2. Load a chat/instruct model in LM Studio and enable its local server.
3. Select a bounded time range, device, local model, and optionally a directory containing Git repositories.
4. Click **Generate timesheet**. Commit subjects plus staged, unstaged, and untracked file metadata from the selected range are included as local classification evidence.
5. Copy the generated timesheet.

Task durations are always derived from ActivityWatch segments. Model-generated durations are not accepted.

Example context redaction:

```bash
export TIMELOGGER_TITLE_REDACT_PATTERNS='ACME-[0-9]+;Customer Name'
export TIMELOGGER_REDACT_DOMAINS='mail.example.com;internal.example.com'
```

## macOS application

The desktop edition wraps the local FastAPI app in a native macOS WebKit window. Its database is stored at `~/Library/Application Support/TimeLogger 3000/timelogger.db`; the HTTP server listens only on a random localhost port and exits with the window.

Build the application and architecture-specific DMG on macOS:

```bash
.venv/bin/pip install -e '.[desktop]'
scripts/build-macos-app.sh
```

For an internet-distributable build, use an Apple Developer ID Application certificate and notarize the DMG:

```bash
export APPLE_SIGNING_IDENTITY='Developer ID Application: Example Company (TEAMID)'
scripts/build-macos-app.sh

xcrun notarytool store-credentials timelogger-notary \
  --apple-id 'developer@example.com' --team-id TEAMID --password APP_SPECIFIC_PASSWORD
export APPLE_NOTARY_PROFILE=timelogger-notary
scripts/notarize-macos-app.sh dist/TimeLogger-3000-0.1.0-arm64.dmg
```

The build is native to the machine architecture. Build and notarize separately on Apple Silicon and Intel unless the full Python/dependency stack is built as universal2.

The macOS package does not include ActivityWatch or LM Studio. Install and start ActivityWatch before opening TimeLogger:

1. Download ActivityWatch from https://activitywatch.net/downloads/
2. Start the ActivityWatch desktop application and grant macOS Accessibility permission when asked.
3. Open TimeLogger and confirm the ActivityWatch status shows connected.

LM Studio remains an external prerequisite. Browser context is optional and can be installed from the official Chrome or Firefox extension store.

## Distribution compliance

ActivityWatch attribution and source-distribution materials are maintained in:

- `THIRD_PARTY_NOTICES.md`
- `licenses/activitywatch/MPL-2.0.txt`
- `compliance/activitywatch-components.json`

Before distributing a release, set its stable corresponding-source URL in the component manifest, generate the source archive, and run the compliance check:

```bash
scripts/build-activitywatch-source-bundle.sh
.venv/bin/python scripts/check-release-compliance.py
```

The optional browser extension should be linked from its official Chrome or Firefox store rather than redistributed.

## Test

```bash
.venv/bin/pytest
```

## Implemented scope

- ActivityWatch and LM Studio connectivity checks
- Canonical events with AFK filtering, merging, and categorization
- Optional active browser context correlation
- Optional recursive Git commit and working-tree metadata collection scoped to the selected time range
- Human-sized timeline blocks that merge title churn and brief interruptions
- Detection of sustained-work boundaries and project switches
- Structured local classification with validation, coverage repair, and retry
- Deterministic task durations and automatic sub-minute task absorption
- Timesheet-oriented consolidation and duration rounding
- Simple project-name correction for undetected projects
- Exact local-AI payload preview
- Structured local summary generation with strict entry-ID validation
- SQLite runs, sanitized segments, tasks, entries, model, and prompt metadata
