# AGENTS.md

## Product

TimeLogger 3000 is a privacy-first local web application. ActivityWatch is the source of truth for time; LM Studio performs all AI processing locally. Optimize the interface for one primary flow: select a range, generate a timesheet, fill only missing project names, and copy/export results.

## UI design source

Use the Linear design-system reference supplied by the project owner:
https://styles.refero.design/style/90ce5883-bb24-4466-93f7-801cd617b0d1

`EXAMPLE.md` is the repository's concrete layout and density reference. Follow its app-shell composition, compact side rail, technical labels, restrained borders, and data-first rows, but do not copy its remote dependencies, decorative controls, fake navigation, avatars, notification UI, or cloud-oriented wording.

North star: **midnight precision instrument**. The UI should feel like a focused desktop tool: quiet, compact, technical, and deliberately engineered. Product data is the visual texture; avoid decorative illustration.

## Color tokens

- `--void: #08090a` — page canvas
- `--carbon: #0f1011` — cards and raised surfaces
- `--obsidian: #17181a` — inputs and subtle surfaces
- `--border: #23252a` — default hairline borders
- `--border-strong: #383b3f` — hover/focus borders
- `--text-primary: #ffffff` — primary headings
- `--text-body: #d0d6e0` — body and secondary headings
- `--text-muted: #8a8f98` — metadata and helper text
- `--text-faint: #62666d` — low-emphasis labels
- `--accent: #a4c9ff` — current project override: primary action and active progress only
- `--success: #27a644` — connection/success status
- `--danger: #eb5757` — failures and destructive states
- `--warning: #a4c9ff` — missing user input (current cool-blue visual override)

Do not introduce additional chromatic accents. Do not use chromatic body copy.

### Current visual override

The project owner selected `EXAMPLE.md` as the active visual direction. Use its restrained cool-blue signal accent (`#a4c9ff`) and related low-opacity blue surfaces instead of the earlier acid-lime accent. This supersedes the acid-lime component guidance below until changed by the owner.

## Typography

- Use `Inter Variable`, `Inter`, then system-ui fallbacks.
- Use weights 400, 510/500, and 590/600. Avoid heavy 700–900 display weights.
- Enable `font-feature-settings: "cv01", "ss03", "zero"` where supported.
- Display/hero: tight tracking around `-0.022em`, line-height 1.
- Section headings: tight tracking around `-0.012em`.
- Body: 14–16px, weight 400, line-height 1.5.
- Technical metadata may use `Berkeley Mono`, `ui-monospace`, or SFMono; do not use mono for headings.

## Shape, spacing, and depth

- Base spacing unit: 4px. Prefer 8, 12, 16, 24, 32, 48, and 96px.
- Page max width: 1200px.
- Card padding: 24px.
- Card radius: 12px maximum.
- Button/input radius: 6px.
- Pills/status badges: fully rounded.
- Separate surfaces using 0.5–1px hairline borders and subtle inset highlights.
- Do not use large soft drop shadows, glows, glass cards, or radii above 12px.

## Components

### Primary action

- Exactly one cool-blue filled primary action per view.
- Background `#a4c9ff`, text `#002a52`, 6px radius, compact 10px 16px padding.
- Secondary buttons are neutral outlines or subtle dark fills.

### Cards

- Carbon surface on Void canvas.
- 1px `#23252a` border or inset ring; no floating shadow.
- Keep information hierarchy clear with dividers, spacing, and typography.

### Inputs

- Obsidian/dark surface, hairline border, white/body text.
- Acid-lime focus border/ring used sparingly.
- Labels are compact muted text above inputs.

### Status

- Compact pills with a small status dot.
- Connected uses green; failure uses red; pending remains neutral.
- Progress uses acid lime because it represents the active primary operation.

## UX rules

- Keep the happy path visible and short.
- Do not expose raw ActivityWatch events or long proposed-task lists.
- Show a clear staged progress indicator during local classification.
- Ask users only for unknown project names; detected projects are read-only by default.
- Do not show recent-run history on the main page.
- Prefer a few human-sized timesheet entries over event-level detail.
- Keep privacy wording explicit: processing runs in local LM Studio.
- Never imply that model-generated durations are authoritative.
- Preserve responsive behavior and accessible labels, focus states, and contrast.
- Localize all user-facing dates and times with the browser locale (`Intl.DateTimeFormat`); never hard-code US date presentation.
- Date/time controls should offer practical presets and an explicit localized range summary while sending timezone-aware ISO timestamps to the backend.

## Implementation rules

- UI files are `app/static/index.html`, `app/static/styles.css`, and `app/static/app.js`.
- Use semantic HTML and no frontend framework unless explicitly requested.
- Keep CSS tokens in `:root`; do not scatter raw colors when a token exists.
- Avoid remote font dependencies; system Inter fallback must work offline.
- Validate JavaScript with `node --check app/static/app.js`.
- Run `.venv/bin/pytest -q` after behavior changes.
