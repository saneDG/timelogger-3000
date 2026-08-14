"""Allow ActivityWatch permission helper subprocesses in a frozen watcher."""

import multiprocessing

multiprocessing.freeze_support()
