"""Native macOS launcher for the local TimeLogger web application."""

import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("TIMELOGGER_DESKTOP", "1")

import uvicorn
import webview


APP_NAME = "TimeLogger 3000"


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_until_ready(url: str, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/status", timeout=1):
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("The local TimeLogger server did not start.")


def main() -> None:
    data_directory = Path.home() / "Library" / "Application Support" / APP_NAME
    data_directory.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TIMELOGGER_DB", str(data_directory / "timelogger.db"))

    # Import only after desktop environment paths are configured. app.main
    # constructs its repository while importing the module.
    from app.main import app

    port = _available_port()
    url = "http://127.0.0.1:%d" % port
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning",
        access_log=False, server_header=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="timelogger-server", daemon=True)
    thread.start()
    try:
        _wait_until_ready(url)
        webview.create_window(
            APP_NAME, url=url, width=1280, height=820,
            min_size=(900, 640), background_color="#08090a",
        )
        webview.start(gui="cocoa", private_mode=False)
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
