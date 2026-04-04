from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI, Request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator

from common.auth import decode_token
from common.config import get_settings


def setup_logging(service_name: str) -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )
    structlog.contextvars.bind_contextvars(service=service_name)


def setup_tracing(service_name: str) -> None:
    settings = get_settings()
    resource = Resource(attributes={"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.jaeger_endpoint + "/v1/traces")))
    trace.set_tracer_provider(provider)
    RedisInstrumentor().instrument()


def setup_app(app: FastAPI, service_name: str, db_engine=None) -> None:
    setup_logging(service_name)
    try:
        setup_tracing(service_name)
    except Exception:
        pass

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        claims = {}
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                claims = decode_token(auth.split(" ", 1)[1])
            except Exception:
                claims = {}

        span = trace.get_current_span()
        if claims and span is not None:
            if claims.get("user_id"):
                span.set_attribute("auth.user_id", claims.get("user_id"))
            if claims.get("system_role"):
                span.set_attribute("auth.system_role", claims.get("system_role"))
            if claims.get("business_role"):
                span.set_attribute("auth.business_role", claims.get("business_role"))

        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-trace-id"] = request.headers.get("x-trace-id", request_id)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        structlog.get_logger().info(
            "http_request",
            request_id=request_id,
            trace_id=response.headers["x-trace-id"],
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            latency_ms=latency_ms,
            user_id=claims.get("user_id"),
            system_role=claims.get("system_role"),
            business_role=claims.get("business_role"),
        )
        return response

    Instrumentator().instrument(app).expose(app)
    FastAPIInstrumentor.instrument_app(app)
    if db_engine is not None:
        try:
            SQLAlchemyInstrumentor().instrument(engine=db_engine.sync_engine)
        except Exception:
            pass
