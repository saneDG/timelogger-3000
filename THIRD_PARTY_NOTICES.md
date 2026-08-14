# Third-party notices

TimeLogger 3000 is an independent project. It is not affiliated with, endorsed by, or maintained by ActivityWatch.

## ActivityWatch Python components currently distributed

TimeLogger 3000 depends on the following ActivityWatch components:

| Component | Version | License | Source |
| --- | --- | --- | --- |
| `aw-client` | 0.5.15 | Mozilla Public License 2.0 | https://github.com/ActivityWatch/aw-client |
| `aw-core` | 0.5.17 | Mozilla Public License 2.0 | https://github.com/ActivityWatch/aw-core |

Copyright belongs to the ActivityWatch contributors. The full Mozilla Public License 2.0 is included at `licenses/activitywatch/MPL-2.0.txt`.

Corresponding source archives for the exact packaged versions can be generated with:

```bash
scripts/build-activitywatch-source-bundle.sh
```

Release builds must publish the generated archive beside the application installer and replace the source placeholder in `compliance/activitywatch-components.json` with its stable release URL.

No ActivityWatch source files are currently modified by TimeLogger 3000. If that changes, the modified MPL-covered files, patch set, and build instructions must be included in the corresponding-source archive.

## ActivityWatch executables not distributed

`aw-server`, `aw-watcher-window`, and `aw-watcher-afk` are external prerequisites. Users install ActivityWatch from its official distribution; this repository does not bundle those executables.

## Browser extension

TimeLogger 3000 should link to the official extension rather than redistribute it:

- Chrome: https://chromewebstore.google.com/detail/activitywatch-web-watcher/nglaklhklhcoonedhgnpgddginnjdadi
- Firefox: https://addons.mozilla.org/en-US/firefox/addon/aw-watcher-web/

The ActivityWatch name and logo are not licensed for use as TimeLogger 3000 branding. References to ActivityWatch describe compatibility and included components only.
