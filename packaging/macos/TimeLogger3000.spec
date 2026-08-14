# Build with: pyinstaller --clean --noconfirm packaging/macos/TimeLogger3000.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPEC).resolve().parents[2]

activitywatch_runtime = ROOT / "build" / "activitywatch-runtime"
if not activitywatch_runtime.is_dir():
    raise SystemExit("Missing bundled ActivityWatch runtime. Run scripts/build-activitywatch-runtime-macos.sh first.")

datas = [
    (str(ROOT / "app" / "static"), "app/static"),
    (str(ROOT / "licenses"), "licenses"),
    (str(ROOT / "compliance"), "compliance"),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(activitywatch_runtime), "activitywatch"),
]
hiddenimports = collect_submodules("uvicorn") + collect_submodules("webview")
for package in ("aw_client", "aw_core", "aw_datastore", "aw_transform"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    hiddenimports += package_hidden

analysis = Analysis(
    [str(ROOT / "app" / "desktop.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PyQt5", "PyQt6", "gtk"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz, analysis.scripts, [],
    exclude_binaries=True, name="TimeLogger 3000", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    target_arch=None, codesign_identity=None,
    entitlements_file=str(ROOT / "packaging" / "macos" / "entitlements.plist"),
)
collection = COLLECT(
    executable, analysis.binaries, analysis.datas,
    strip=False, upx=False, name="TimeLogger 3000",
)
app = BUNDLE(
    collection,
    name="TimeLogger 3000.app",
    icon=str(ROOT / "packaging" / "macos" / "TimeLogger.icns"),
    bundle_identifier="com.timelogger3000.app",
    info_plist={
        "CFBundleDisplayName": "TimeLogger 3000",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright © 2026 TimeLogger 3000 contributors",
        "NSAppleEventsUsageDescription": "TimeLogger uses a native folder picker and reads active application metadata for your local timesheet.",
        "NSAccessibilityUsageDescription": "TimeLogger tracks the active application and idle state locally to build your timesheet.",
    },
)
