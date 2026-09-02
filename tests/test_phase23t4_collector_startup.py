import asyncio
import threading

import pytest


def test_lifespan_starts_scheduler_before_yield_and_keeps_event_loop_responsive(
    monkeypatch,
):
    import api.main as main

    events = []
    started = threading.Event()
    release = threading.Event()
    yielded = threading.Event()

    class FakeDatabase:
        def initialize(self):
            events.append("database_initialize")

    class FakeScheduler:
        def start(self, initial_collection=True):
            events.append(("scheduler_start", initial_collection))
            started.set()
            release.wait(timeout=5)
            events.append("scheduler_start_complete")

        def stop(self):
            events.append("scheduler_stop")

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "AODP_NATS_ENABLED", False)
    monkeypatch.setattr(main, "scheduler", FakeScheduler())

    async def run_lifespan():
        async with main.lifespan(main.app):
            yielded.set()

    async def run_test():
        lifespan_task = asyncio.create_task(run_lifespan())

        await asyncio.to_thread(started.wait, 5)

        assert ("scheduler_start", True) in events
        assert not yielded.is_set()

        observer_ran = False

        async def observer():
            nonlocal observer_ran
            observer_ran = True

        await observer()

        assert observer_ran is True
        assert not yielded.is_set()

        release.set()
        await asyncio.wait_for(lifespan_task, timeout=5)

        assert "scheduler_start_complete" in events
        assert yielded.is_set()
        assert events[-1] == "scheduler_stop"

    asyncio.run(run_test())


def test_lifespan_propagates_scheduler_start_exception(monkeypatch):
    import api.main as main

    events = []

    class FakeDatabase:
        def initialize(self):
            events.append("database_initialize")

    class FakeScheduler:
        def start(self, initial_collection=True):
            events.append(("scheduler_start", initial_collection))
            raise RuntimeError("initial collection failed")

        def stop(self):
            events.append("scheduler_stop")

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "AODP_NATS_ENABLED", False)
    monkeypatch.setattr(main, "scheduler", FakeScheduler())

    async def run_test():
        with pytest.raises(RuntimeError, match="initial collection failed"):
            async with main.lifespan(main.app):
                pytest.fail("lifespan yielded before scheduler.start completed")

    asyncio.run(run_test())

    assert ("scheduler_start", True) in events
    assert "scheduler_stop" in events
