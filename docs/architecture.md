# Architecture

EasyITLab Bank is a microservice-based educational platform.

## Main Components

- `frontend-cabinet`: student web UI
- `api-gateway`: single API entrypoint
- `auth-service`: authentication and token operations
- `bank-api`: business domain operations
- `postgres`: transactional data store
- `redis`: cache and transient state
- `kafka`: event streaming
- `jenkins`: CI training job execution

## Request Flow

1. User authenticates via `auth-service`.
2. Client calls APIs through `api-gateway`.
3. Business actions are handled in `bank-api`.
4. Data is persisted in PostgreSQL.
5. Cache and short-lived state use Redis.
6. Domain events are emitted to Kafka.

## Environment

For local development, all services run through Docker Compose.
