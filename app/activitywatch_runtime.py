"""Lifecycle manager for ActivityWatch components embedded in the macOS app."""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


class BundledActivityWatch:
    def __init__(
        self, data_directory: Path, host: str = "127.0.0.1", port: int = 5600,
        runtime_directory: Optional[Path] = None,
    ):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        self.runtime = runtime_directory or root / "activitywatch"
        self.data_directory = data_directory / "ActivityWatch"
        self.host = host
        self.port = port
        self.processes: List[subprocess.Popen] = []
        self.log_files = []
        self.started = False

    @property
    def available(self) -> bool:
        return all(
            path.exists()
            for path in (
                self.runtime / "aw-server" / "aw-server",
                self.runtime / "aw-watcher-window" / "aw-watcher-window",
                self.runtime / "aw-watcher-afk" / "aw-watcher-afk",
            )
        )

    def _server_reachable(self) -> bool:
        try:
            with urllib.request.urlopen(
                "http://%s:%s/api/0/info" % (self.host, self.port), timeout=0.5
            ):
                return True
        except Exception:
            return False

    def _required_buckets_ready(self) -> bool:
        try:
            with urllib.request.urlopen(
                "http://%s:%s/api/0/buckets/" % (self.host, self.port), timeout=0.5
            ) as response:
                bucket_ids = set(json.load(response))
            has_window = any(item.startswith("aw-watcher-window_") for item in bucket_ids)
            has_afk = any(item.startswith("aw-watcher-afk_") for item in bucket_ids)
            return has_window and has_afk
        except Exception:
            return False

    def _environment(self) -> Dict[str, str]:
        environment = os.environ.copy()
        home = self.data_directory / "home"
        home.mkdir(parents=True, exist_ok=True)
        environment["HOME"] = str(home)
        environment["PYTHONUNBUFFERED"] = "1"
        return environment

    def _launch(self, name: str, command: List[str], cwd: Optional[Path] = None) -> None:
        logs = self.data_directory / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        log = open(logs / (name + ".log"), "ab", buffering=0)
        self.log_files.append(log)
        self.processes.append(
            subprocess.Popen(
                command, cwd=str(cwd) if cwd else None, env=self._environment(),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        )

    def start(self) -> str:
        if self._server_reachable():
            return "external"
        if not self.available:
            return "unavailable"
        self.data_directory.mkdir(parents=True, exist_ok=True)
        server_directory = self.runtime / "aw-server"
        self._launch(
            "server",
            [
                str(server_directory / "aw-server"), "--host", self.host,
                "--port", str(self.port),
            ],
            server_directory,
        )
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline and not self._server_reachable():
            if self.processes[0].poll() is not None:
                break
            time.sleep(0.15)
        if not self._server_reachable():
            self.stop()
            return "failed"
        for name in ("window", "afk"):
            directory = self.runtime / ("aw-watcher-" + name)
            command = [
                str(directory / ("aw-watcher-" + name)),
                "--host", self.host, "--port", str(self.port),
            ]
            if name == "window":
                command.extend(["--strategy", "jxa"])
            self._launch(name, command, directory)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline and not self._required_buckets_ready():
            if any(process.poll() is not None for process in self.processes[1:]):
                break
            time.sleep(0.2)
        self.started = True
        return "bundled" if self._required_buckets_ready() else "bundled_degraded"

    def stop(self) -> None:
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 4
        for process in reversed(self.processes):
            remaining = max(0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()
        self.processes.clear()
        for log in self.log_files:
            log.close()
        self.log_files.clear()
        self.started = False
