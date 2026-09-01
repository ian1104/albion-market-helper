import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient


def test_fastapi_lifespan_starts_and_stops_nats_collectors(monkeypatch):
    import api.main as main

    events = []

    class FakeConsumer:
        def __init__(self, adapter, database, *, server, nats_url, subject):
            self.server = server
            self._client = None
            self.messages_received = 0
            self.orders_saved = 0
            self.invalid_messages = 0
            self.connection_attempts = 0
            self.reconnect_count = 0
            self.subscription_active = False
            self.last_message_at = None
            self.last_successful_persistence = None
            self.last_error = None
            events.append(("create", server))

        async def start(self):
            self.subscription_active = True
            self.connection_attempts += 1
            events.append(("start", self.server))
            await asyncio.Event().wait()

        async def stop(self):
            self.subscription_active = False
            events.append(("stop", self.server))

    monkeypatch.setattr(main, "AODP_NATS_ENABLED", True)
    monkeypatch.setattr(main, "AODP_NATS_SERVERS", ("east", "west", "europe"))
    monkeypatch.setattr(main, "AODPNatsConsumer", FakeConsumer)

    with TestClient(main.app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert set(main.nats_consumers) == {"east", "west", "europe"}
        assert all(main.nats_tasks.values())
        assert all(c.subscription_active for c in main.nats_consumers.values())

    assert [event[0] for event in events].count("create") == 3
    assert [event[0] for event in events].count("start") == 3
    assert [event[0] for event in events].count("stop") == 3
    assert main.nats_consumers == {}
    assert main.nats_tasks == {}


def test_liquidity_status_exposes_live_consumer_state(monkeypatch):
    import api.main as main

    consumer = SimpleNamespace(
        _client=SimpleNamespace(is_closed=False),
        messages_received=17,
        orders_saved=15,
        invalid_messages=2,
        connection_attempts=2,
        reconnect_count=1,
        subscription_active=True,
        last_message_at="2026-09-01T00:00:00+00:00",
        last_successful_persistence="2026-09-01T00:00:01+00:00",
        last_error=None,
    )
    monkeypatch.setitem(main.nats_consumers, "east", consumer)
    monkeypatch.setattr(main, "AODP_NATS_ENABLED", True)
    monkeypatch.setattr(main, "AODP_NATS_SERVERS", ("east",))
    monkeypatch.setattr(main.lifecycle_manager, "refresh", lambda *, server: {"ACTIVE": 1})

    payload = main.liquidity_status("east")
    assert payload["connected"] is True
    assert payload["messages_received"] == 17
    assert payload["orders_saved"] == 15
    assert payload["invalid_messages"] == 2
    assert payload["connection_attempts"] == 2
    assert payload["reconnect_count"] == 1
    assert payload["subscription_active"] is True
    assert payload["last_message_at"] == "2026-09-01T00:00:00+00:00"
    assert payload["last_successful_persistence"] == "2026-09-01T00:00:01+00:00"
