from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaProducer

from common.config import get_settings

settings = get_settings()
producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    global producer
    if producer is None:
        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await producer.start()
    return producer


async def produce_event(topic: str, event_type: str, payload: dict[str, Any], key: str | None = None, idempotency_key: str | None = None) -> None:
    kafka = await get_producer()
    event = {
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "event_version": "1",
        "occurred_at": datetime.now(UTC).isoformat(),
        "trace_id": payload.get("trace_id"),
        "payload": payload,
        "key": key,
        "idempotency_key": idempotency_key,
    }
    await kafka.send_and_wait(topic, json.dumps(event).encode("utf-8"), key=(key or event_type).encode("utf-8"))


async def close_producer() -> None:
    global producer
    if producer is not None:
        await producer.stop()
        producer = None
