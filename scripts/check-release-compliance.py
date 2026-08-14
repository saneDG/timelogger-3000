#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "compliance/activitywatch-components.json").read_text())
pyproject = (ROOT / "pyproject.toml").read_text()
errors = []

required = [
    ROOT / "THIRD_PARTY_NOTICES.md",
    ROOT / "licenses/activitywatch/MPL-2.0.txt",
    ROOT / "compliance/activitywatch-components.json",
]
for path in required:
    if not path.is_file():
        errors.append("Missing required compliance file: %s" % path.relative_to(ROOT))

required_components = {"aw-client", "aw-core"}
manifest_components = {item["name"] for item in manifest["distributed_components"]}
missing_components = required_components - manifest_components
if missing_components:
    errors.append("Missing distributed ActivityWatch components: %s" % ", ".join(sorted(missing_components)))

for component in manifest["distributed_components"]:
    name, version = component["name"], component["version"]
    if not re.search(r'"%s==%s"' % (re.escape(name), re.escape(version)), pyproject):
        # aw-core is a transitive dependency of aw-client and is intentionally
        # absent from project dependencies, but it must remain in the manifest.
        if name != "aw-core":
            errors.append("pyproject.toml does not pin %s==%s" % (name, version))

if manifest["release_source_archive_url"].startswith("REPLACE_"):
    errors.append("Set release_source_archive_url before distributing a release.")

if errors:
    raise SystemExit("\n".join("ERROR: " + error for error in errors))
print("ActivityWatch release compliance checks passed.")
