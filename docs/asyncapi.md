# AsyncAPI

AsyncAPI in this project is the event-driven equivalent of Swagger/OpenAPI.

If Swagger describes:

- HTTP paths
- request and response bodies
- authentication for REST calls

then AsyncAPI describes:

- Kafka brokers
- topics
- published event types
- event envelope and payload schemas
- examples for producers and consumers

## Local URLs

- HTML docs: `http://127.0.0.1:8090/`
- Raw spec: `http://127.0.0.1:8090/asyncapi.yaml`
- Kafka broker for host clients: `127.0.0.1:9092`
- Kafka broker inside docker-compose: `kafka:9092`

## Main topics

- `auth-events`
- `iam-events`
- `client-events`
- `account-events`
- `card-events`
- `transfer-events`
- `support-events`
- `bank-events`
- `usage-events`
- `audit-events`
- `student-events`

## Source of truth

- AsyncAPI spec source: [asyncapi.yaml](./asyncapi.yaml)
- Kafka producer envelope: [../services/common/kafka.py](../services/common/kafka.py)
- Event publishing helper: [../services/bank-api/app/main.py](../services/bank-api/app/main.py)

## Start locally

```bash
make up
make migrate
```

Then open `http://127.0.0.1:8090/`.
