import asyncio
import types

from core import mcp_executor


class _AliveThread:
    def is_alive(self):
        return True

    def join(self, timeout=None):
        return None


class _LoopStub:
    def __init__(self):
        self.running = True
        self.closed = False

    def is_running(self):
        return self.running

    def call_soon_threadsafe(self, callback):
        callback()

    def stop(self):
        self.running = False

    def is_closed(self):
        return self.closed

    def close(self):
        self.closed = True


class _ResultFuture:
    def __init__(self, value):
        self._value = value

    def result(self, timeout=None):
        return self._value


def test_service_executor_restarts_background_loop_after_shutdown_error(monkeypatch):
    monkeypatch.setenv("DEV_ALLOW_DIRECT_SERVER", "1")
    executor = mcp_executor.ServiceExecutor()
    executor._use_gateway = False
    executor._loop = _LoopStub()
    executor._thread = _AliveThread()

    restart_count = {"count": 0}

    def fake_start():
        restart_count["count"] += 1
        executor._loop = _LoopStub()
        executor._thread = _AliveThread()

    monkeypatch.setattr(executor, "start", fake_start)
    monkeypatch.setattr(executor, "_service_manager", types.SimpleNamespace(discover_services=lambda: None))
    monkeypatch.setattr(mcp_executor.time, "sleep", lambda _seconds: None)

    calls = {"count": 0}

    def fake_run_coroutine_threadsafe(coro, loop):
        calls["count"] += 1
        if calls["count"] == 1:
            coro.close()
            raise RuntimeError("cannot schedule new futures after shutdown")
        coro.close()
        return _ResultFuture({"status": "ok"})

    monkeypatch.setattr(
        mcp_executor.asyncio,
        "run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    result = executor.submit_call(
        "dummy_api",
        "sync_notes",
        {"user_id": "1"},
        timeout=10,
        use_gateway=False,
    )

    assert result == {"status": "ok"}
    assert restart_count["count"] == 1
    assert calls["count"] == 2


def test_service_executor_restarts_background_loop_after_interpreter_shutdown_error(monkeypatch):
    monkeypatch.setenv("DEV_ALLOW_DIRECT_SERVER", "1")
    executor = mcp_executor.ServiceExecutor()
    executor._use_gateway = False
    executor._loop = _LoopStub()
    executor._thread = _AliveThread()

    restart_count = {"count": 0}

    def fake_start():
        restart_count["count"] += 1
        executor._loop = _LoopStub()
        executor._thread = _AliveThread()

    monkeypatch.setattr(executor, "start", fake_start)
    monkeypatch.setattr(executor, "_service_manager", types.SimpleNamespace(discover_services=lambda: None))
    monkeypatch.setattr(mcp_executor.time, "sleep", lambda _seconds: None)

    calls = {"count": 0}

    def fake_run_coroutine_threadsafe(coro, loop):
        calls["count"] += 1
        if calls["count"] == 1:
            coro.close()
            raise RuntimeError("cannot schedule new futures after interpreter shutdown")
        coro.close()
        return _ResultFuture({"status": "ok"})

    monkeypatch.setattr(
        mcp_executor.asyncio,
        "run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    result = executor.submit_call(
        "dummy_api",
        "sync_notes",
        {"user_id": "1"},
        timeout=10,
        use_gateway=False,
    )

    assert result == {"status": "ok"}
    assert restart_count["count"] == 1
    assert calls["count"] == 2
