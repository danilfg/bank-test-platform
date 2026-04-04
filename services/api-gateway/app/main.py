from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse

from common.observability import setup_app

AUTH_URL = "http://auth-service:8001"
BANK_URL = "http://bank-api:8002"
SWAGGER_TOP_DESCRIPTION = """
Developed by Daniil Nikolaev

Cloud version of the platform for QA, backend, and DevOps practice with all 10+ tools - [bank.easyitlab.tech](https://bank.easyitlab.tech)

Contact via email [easyitwithdaniil@gmail.com](mailto:easyitwithdaniil@gmail.com) or Telegram [@danilfg](https://t.me/danilfg)

Join the community: [chat.easyitlab.tech](https://chat.easyitlab.tech)

## Base Path

`http://127.0.0.1:8080`

## How To Get Access Token

1. Request token via login:

```bash
curl -sS -X POST "http://127.0.0.1:8080/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"student@easyitlab.tech","password":"student123"}'
```

2. Copy `access_token` from response.
""".strip()

app = FastAPI(
    title="EasyBank API Gateway",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
setup_app(app, "api-gateway")

rate_windows: dict[str, deque[float]] = defaultdict(deque)
openapi_cache: dict[str, tuple[float, dict]] = {}
OPENAPI_CACHE_TTL_SECONDS = 15


def pick_target(path: str) -> str:
    if path.startswith("/auth"):
        return AUTH_URL
    return BANK_URL


def rate_key(request: Request) -> str:
    auth = request.headers.get("authorization")
    if auth:
        return auth
    if request.client:
        return request.client.host
    return "anonymous"


def enforce_rate_limit(request: Request, scope: str, limit: int, window_seconds: int) -> None:
    key = f"{scope}:{rate_key(request)}"
    now = time.time()
    bucket = rate_windows[key]
    while bucket and (now - bucket[0]) > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise ValueError(f"{scope}: {limit}/{window_seconds}s")
    bucket.append(now)


def _merge_openapi_specs(specs: list[dict], server_url: str) -> dict:
    merged: dict = {
        "openapi": "3.1.0",
        "info": {"title": "EasyBank Aggregated API", "version": "1.0.0", "description": SWAGGER_TOP_DESCRIPTION},
        "servers": [{"url": server_url}],
        "paths": {},
        "components": {"schemas": {}, "securitySchemes": {}},
        "tags": [],
    }
    tags_seen: set[str] = set()

    for spec in specs:
        for path, item in spec.get("paths", {}).items():
            merged["paths"][path] = item

        components = spec.get("components", {})
        for schema_name, schema in components.get("schemas", {}).items():
            if schema_name not in merged["components"]["schemas"]:
                merged["components"]["schemas"][schema_name] = schema
        for sec_name, sec in components.get("securitySchemes", {}).items():
            if sec_name not in merged["components"]["securitySchemes"]:
                merged["components"]["securitySchemes"][sec_name] = sec

        for tag in spec.get("tags", []):
            name = tag.get("name")
            if name and name not in tags_seen:
                tags_seen.add(name)
                merged["tags"].append(tag)

    # FastAPI may omit top-level tags; infer them from operations so Swagger groups are visible.
    if not merged["tags"]:
        inferred_tags: set[str] = set()
        for methods in merged["paths"].values():
            if not isinstance(methods, dict):
                continue
            for operation in methods.values():
                if not isinstance(operation, dict):
                    continue
                for name in operation.get("tags", []):
                    if isinstance(name, str) and name:
                        inferred_tags.add(name)
        merged["tags"] = [{"name": name} for name in sorted(inferred_tags)]

    return merged


def _normalize_openapi_schemas(spec: dict) -> dict:
    for _, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for _, operation in methods.items():
            if not isinstance(operation, dict):
                continue

            request_body = operation.get("requestBody", {})
            if isinstance(request_body, dict):
                content = request_body.get("content", {})
                if isinstance(content, dict):
                    for _, media in content.items():
                        if isinstance(media, dict) and media.get("schema", None) == {}:
                            media["schema"] = {"type": "object", "additionalProperties": True, "example": {}}

            responses = operation.get("responses", {})
            if isinstance(responses, dict):
                for _, response in responses.items():
                    if not isinstance(response, dict):
                        continue
                    content = response.get("content", {})
                    if not isinstance(content, dict):
                        continue
                    for _, media in content.items():
                        if not isinstance(media, dict):
                            continue
                        schema = media.get("schema")
                        if schema == {}:
                            media["schema"] = {"type": "object", "additionalProperties": True, "example": {}}
                        elif isinstance(schema, dict) and schema.get("type") == "array" and "items" not in schema:
                            schema["items"] = {"type": "object", "additionalProperties": True}

    return spec


def _external_base_url(request: Request) -> str:
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}".rstrip("/")


async def _build_gateway_openapi(server_url: str) -> dict:
    now = time.time()
    cached = openapi_cache.get(server_url)
    if cached and (now - cached[0]) < OPENAPI_CACHE_TTL_SECONDS:
        return cached[1]

    specs: list[dict] = []
    async with httpx.AsyncClient(timeout=15) as client:
        for url in (f"{AUTH_URL}/openapi.json", f"{BANK_URL}/openapi.json"):
            resp = await client.get(url)
            resp.raise_for_status()
            specs.append(resp.json())

    merged = _merge_openapi_specs(specs, server_url)
    merged = _normalize_openapi_schemas(merged)
    openapi_cache[server_url] = (now, merged)
    return merged


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ok"}


@app.get("/openapi.json")
async def openapi_json(request: Request):
    try:
        return await _build_gateway_openapi(_external_base_url(request))
    except Exception:
        return {
            "openapi": "3.1.0",
            "info": {"title": "Легко в ИТ банк API", "version": "1.0.0", "description": SWAGGER_TOP_DESCRIPTION},
            "paths": {},
            "components": {"schemas": {}, "securitySchemes": {}},
            "x_error": "Failed to load upstream openapi specs",
        }


@app.get("/docs")
async def swagger_docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="EasyBank API Docs",
        swagger_ui_parameters={"persistAuthorization": True},
    )


@app.get("/redoc")
async def redoc_docs():
    return get_redoc_html(openapi_url="/openapi.json", title="EasyBank API ReDoc")


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], include_in_schema=False)
async def gateway(full_path: str, request: Request):
    path = "/" + full_path

    try:
        if path == "/auth/login" and request.method == "POST":
            enforce_rate_limit(request, "login", 5, 60)
        if path == "/auth/refresh" and request.method == "POST":
            enforce_rate_limit(request, "refresh", 10, 60)
        if path.startswith("/clients/me/transfers") and request.method == "POST":
            enforce_rate_limit(request, "transfer_create", 20, 60)
    except ValueError as exc:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests",
                    "details": {"limit": str(exc)},
                    "request_id": request.headers.get("x-request-id", ""),
                    "trace_id": request.headers.get("x-trace-id", ""),
                }
            },
        )

    target = pick_target(path)
    headers = dict(request.headers)
    request_id = headers.get("x-request-id") or uuid.uuid4().hex
    headers["x-request-id"] = request_id
    headers["x-trace-id"] = headers.get("x-trace-id", request_id)

    body = await request.body()
    async with httpx.AsyncClient(timeout=30) as client:
        upstream = await client.request(
            method=request.method,
            url=f"{target}{path}",
            params=request.query_params,
            headers=headers,
            content=body,
        )

    response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in {"transfer-encoding", "connection", "content-encoding", "content-length"}
    }
    response_headers["x-request-id"] = request_id
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)
