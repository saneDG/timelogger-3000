from pathlib import Path

from app.activitywatch_runtime import BundledActivityWatch


def test_reuses_existing_activitywatch_server(tmp_path: Path, monkeypatch):
    runtime = BundledActivityWatch(tmp_path, runtime_directory=tmp_path / "missing")
    monkeypatch.setattr(runtime, "_server_reachable", lambda: True)

    assert runtime.start() == "external"
    assert runtime.processes == []


def test_stop_terminates_managed_processes_and_closes_logs(tmp_path: Path):
    runtime = BundledActivityWatch(tmp_path, runtime_directory=tmp_path)

    class Process:
        def __init__(self):
            self.terminated = False
            self.killed = False

        def poll(self):
            return 0 if self.terminated or self.killed else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.killed = True

    class Log:
        closed = False

        def close(self):
            self.closed = True

    processes = [Process(), Process(), Process()]
    log = Log()
    runtime.processes = processes
    runtime.log_files = [log]
    runtime.started = True

    runtime.stop()

    assert all(process.terminated for process in processes)
    assert log.closed
    assert runtime.processes == []
    assert not runtime.started
