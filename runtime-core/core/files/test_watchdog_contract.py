from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


def _load_watchdog_module(monkeypatch):
    watchdog_package = types.ModuleType("watchdog")
    watchdog_package.__path__ = []  # type: ignore[attr-defined]
    observers_module = types.ModuleType("watchdog.observers")
    events_module = types.ModuleType("watchdog.events")

    class FakeObserver:
        def schedule(self, *args, **kwargs):
            return None

        def start(self):
            return None

        def stop(self):
            return None

        def join(self):
            return None

    class FakeFileSystemEventHandler:
        pass

    observers_module.Observer = FakeObserver
    events_module.FileSystemEventHandler = FakeFileSystemEventHandler

    monkeypatch.setitem(sys.modules, "watchdog", watchdog_package)
    monkeypatch.setitem(sys.modules, "watchdog.observers", observers_module)
    monkeypatch.setitem(sys.modules, "watchdog.events", events_module)
    sys.modules.pop("core.files.watchdog", None)
    return importlib.import_module("core.files.watchdog")


def test_directory_monitor_uses_scheduled_task_default_callback(monkeypatch):
    module = _load_watchdog_module(monkeypatch)
    callback_calls = []

    scheduled_task_module = types.ModuleType("api.rest.services.scheduled_task")

    def fake_process_file_async(file_path, user_id="my"):
        callback_calls.append((file_path, user_id))

    scheduled_task_module.process_file_async = fake_process_file_async
    monkeypatch.setitem(sys.modules, "api.rest.services.scheduled_task", scheduled_task_module)
    monkeypatch.setattr(module, "get_file_content_type", lambda _: "text/plain")

    class ImmediateThread:
        def __init__(self, target, args=(), kwargs=None):
            self.target = target
            self.args = args
            self.kwargs = kwargs or {}

        def start(self):
            self.target(*self.args, **self.kwargs)

    monkeypatch.setattr(module.threading, "Thread", ImmediateThread)

    monitor = module.DirectoryMonitor("/tmp", "user-7")
    monitor.event_handler.on_created(
        SimpleNamespace(is_directory=False, src_path="/tmp/report.txt")
    )

    assert callback_calls == [("/tmp/report.txt", "user-7")]


def test_directory_monitor_preserves_four_argument_callbacks(monkeypatch):
    module = _load_watchdog_module(monkeypatch)
    callback_calls = []
    monkeypatch.setattr(module, "get_file_content_type", lambda _: "text/plain")

    class ImmediateThread:
        def __init__(self, target, args=(), kwargs=None):
            self.target = target
            self.args = args
            self.kwargs = kwargs or {}

        def start(self):
            self.target(*self.args, **self.kwargs)

    monkeypatch.setattr(module.threading, "Thread", ImmediateThread)

    def on_created(file_path, account_id, path, source_type):
        callback_calls.append((file_path, account_id, path, source_type))

    monitor = module.DirectoryMonitor("/watched", 42, on_created_callback=on_created)
    monitor.event_handler.on_created(
        SimpleNamespace(is_directory=False, src_path="/watched/file.md")
    )

    assert callback_calls == [("/watched/file.md", 42, "/watched", "file")]
