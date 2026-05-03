# Local Setup

## Prerequisites

- Docker and Docker Compose
- Make (optional, recommended)

## Start

```bash
make up
make migrate
```

Optional demo reseed:

```bash
make seed
```

## Access

- Student Cabinet: `http://127.0.0.1:5174/`
- API Gateway / Swagger: `http://127.0.0.1:8080/docs`
- AsyncAPI / Kafka event docs: `http://127.0.0.1:8090/`
- Jenkins: `http://127.0.0.1:8086/`

## Credentials

- Email: `student@easyitlab.tech`
- Password: `student123`

## Reset Everything

```bash
make down
make up
make migrate
make seed
```
