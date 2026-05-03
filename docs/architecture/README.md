# BANK Architecture

This folder contains the architecture artifacts for **EasyITLab Bank Open Source**.

## Files

- `bank_architecture.drawio` - editable source diagram for diagrams.net / draw.io.
- `bank_architecture.png` - rendered image for README/documentation embedding.

## Architecture Overview

The architecture is split into layered zones so students can map each operation to the right technical boundary:

1. **User Layer**
   - `Student` as the primary actor.

2. **Frontend Layer**
   - `Student Cabinet` (React + Vite).
   - Handles user workflows: employees, clients, bank data, Jenkins trigger, Swagger usage, and infra interactions.

3. **API Layer**
   - `Bank API` (FastAPI).
   - Main modules: Auth, Clients, Accounts, Cards, Transfers, Support Tickets, Audit Logs, Resource Usage.

4. **Infrastructure Layer**
   - `PostgreSQL` for persistent transactional data.
   - `Redis` for cache/session and transient coordination.
   - `Kafka` for asynchronous event streaming.
   - `AsyncAPI` for Kafka topic and event contract documentation.
   - `Jenkins` for CI job execution.
   - `Swagger / OpenAPI` for API contract and docs.

5. **Observability Layer**
   - Audit Logs.
   - Student Observable Events.
   - Resource Usage Tracker.

6. **Identity / Authentication Layer**
   - Student Users, Student Sessions, Refresh Tokens, Student Identities, Student Identity Accesses.

7. **Bank Domain Model Layer**
   - Banks, Clients, Accounts, Cards, Transfers, Support Tickets.

## Main Flows

- `Student -> Frontend`
- `Frontend -> REST API`
- `REST API -> PostgreSQL`
- `REST API -> Redis`
- `REST API -> Kafka`
- `Kafka -> AsyncAPI docs`
- `Jenkins -> API`
- `Swagger -> API`

## Preview

[<img src="bank_architecture.png" alt="EasyITLab Bank Architecture" width="1200" />](bank_architecture.png)
