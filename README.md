# EasyITLab Bank

![CI](https://github.com/danilfg/bank-open-source/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-Source%20Available-blue)

![Stars](https://img.shields.io/github/stars/danilfg/bank-open-source)
![Forks](https://img.shields.io/github/forks/danilfg/bank-open-source)

![Jenkins](https://img.shields.io/badge/Jenkins-CI-D24939?logo=jenkins&logoColor=white)
![Allure](https://img.shields.io/badge/Allure-Reports-ff6f00)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql&logoColor=white)
![REST API / Swagger](https://img.shields.io/badge/REST%20API%20%2F%20Swagger-Docs-85ea2d?logo=swagger&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?logo=redis&logoColor=white)
![Kafka](https://img.shields.io/badge/Kafka-Events-231F20?logo=apachekafka&logoColor=white)

Educational banking platform for learning:

- API testing
- automation testing
- DevTools debugging
- microservice testing

## Screenshots

Click any preview to open full size.

| Dashboard | Clients |
| --- | --- |
| [<img src="docs/screenshots/dashboard.png" alt="Dashboard" width="420" />](docs/screenshots/dashboard.png) | [<img src="docs/screenshots/clients.png" alt="Clients" width="420" />](docs/screenshots/clients.png) |

| API | API (Alt 1) |
| --- | --- |
| [<img src="docs/screenshots/api.png" alt="API" width="420" />](docs/screenshots/api.png) | [<img src="docs/screenshots/api_2.png" alt="API Alt 1" width="420" />](docs/screenshots/api_2.png) |

## Demo

| Demo | GIF |
| --- | --- |
| Platform walkthrough | [<img src="docs/demo/demo.gif" alt="Platform walkthrough" width="360" />](docs/demo/demo.gif) |
| Jenkins | TBD `docs/demo/jenkins.gif` |
| Allure | TBD `docs/demo/allure.gif` |
| PostgreSQL | TBD `docs/demo/postgresql.gif` |
| Redis | TBD `docs/demo/redis.gif` |
| Kafka | TBD `docs/demo/kafka.gif` |
| REST API / Swagger | `docs/demo/swagger.gif` |

## Features

- realistic banking entities
- student environment
- REST API
- Swagger documentation
- testing playground

## Tooling Overview

This project includes six operational tools not as "extras", but as core parts of the training workflow.
Each tool solves a specific engineering problem:

### Jenkins

Jenkins is used to run reproducible CI jobs from a user-provided GitHub repository.
In this project, it is the execution layer for external test suites and report generation.
By default, tests are pulled from: `https://github.com/danilfg/bank-open-source-tests`.
You can start bank services with Docker, clone your own test repository, and run your own tests in the Jenkins job.

Current metrics:

- preconfigured training jobs: `1` (`training-github-allure`)
- parameters supported in the job: repository URL, branch, test command

GIF: `docs/demo/jenkins.gif`

### Allure

Allure is used to convert raw test results into a readable test analytics report.
In this project, Allure is generated from Jenkins builds and archived as build artifacts.

Current metrics:

- default report generation flow: `1` Jenkins training job
- report artifact path pattern: `/job/<job>/<build>/artifact/allure-report/index.html`

GIF: `docs/demo/allure.gif`

### PostgreSQL

PostgreSQL is the primary transactional database for all persistent business entities:
users, clients, accounts, transfers, tickets, sessions, and identity/access records.

Current metrics:

- public tables in local database: `17` (including migration table)
- domain entities in `docs/db_schema.puml`: `16`
- default database name: `demobank`

GIF: `docs/demo/postgresql.gif`

### Redis

Redis is used for fast transient state: locks, short-lived counters, cache-like state, and session-adjacent operational data.
In this project, it is also used for generation lock control and fast runtime coordination.

Current metrics:

- configured logical Redis databases: `16`
- database used by services: `0` (`redis://redis:6379/0`)

GIF: `docs/demo/redis.gif`

### Kafka

Kafka is used as the event backbone between services.
Business and platform events are emitted for auditability, observability, and async integration patterns.

Current metrics:

- platform event topics in codebase: `11`
- topics: `account-events`, `audit-events`, `auth-events`, `bank-events`, `card-events`, `client-events`, `iam-events`, `student-events`, `support-events`, `transfer-events`, `usage-events`

GIF: `docs/demo/kafka.gif`

### REST API / Swagger

Swagger is used as the live API contract and operational documentation surface.
It is the fastest way to inspect available endpoints, payload formats, and auth requirements.

Current metrics (aggregated gateway OpenAPI):

- API paths: `81`
- HTTP methods/operations: `97`
- student-scoped paths: `31`
- student-scoped operations: `37`

GIF: `docs/demo/swagger.gif`

## Database Schema

Database schema diagram from docs:

[<img src="docs/db-schema.png" alt="Database Schema" width="720" />](docs/db-schema.png)

Source files:

- PlantUML source: [docs/db_schema.puml](docs/db_schema.puml)
- GraphML source: [docs/db-schema.graphml](docs/db-schema.graphml)

## Quick Start

Clone repository:

```bash
git clone https://github.com/danilfg/bank-open-source.git
```

Enter project folder:

```bash
cd bank-open-source
```

Run with Docker:

```bash
docker compose up
```

## API

Example base API:

```text
https://api.bank.easyitlab.tech
```

Example login request:

```text
POST /auth/login
```

## Online Services

Main website:

https://easyitlab.tech/

Cloud version (full functionality):

https://bank.easyitlab.tech/

Community Telegram:

https://t.me/danilfg

## Why this project exists

This platform helps developers learn:

- QA automation
- API testing
- DevTools
- backend debugging

## Contributing

Contributions are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is source-available.

Free for:

- education
- personal use
- research

Commercial use is prohibited.

See [LICENSE](LICENSE).

If this project helps you, please consider giving it a star on GitHub.
