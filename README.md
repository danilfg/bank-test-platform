# BANK: Minimal Student-Only Open Source

Минимальная open-source версия BANK только для студента.

## Что оставлено
- Frontend: `frontends/cabinet` (студкабинет на `http://127.0.0.1:5174/`)
- Backend: `api-gateway`, `auth-service`, `bank-api`
- Infra: PostgreSQL, Redis, Kafka, Jenkins
- Student features:
  - Login / Logout
  - Dashboard
  - Employees
  - Clients
  - Generate entities (в Employees и Clients)
  - Jenkins
  - PostgreSQL
  - REST API / Swagger
  - i18n EN/RU (EN по умолчанию)

## Доступ
- Email: `student@easyitlab.tech`
- Password: `student123`

Это единственная учетная запись для open-source версии.

## Быстрый запуск
1. Поднять окружение:
```bash
make up
```
2. Применить миграции:
```bash
make migrate
```
3. (Опционально) выполнить seed для полной очистки и пересоздания demo-данных:
```bash
make seed
```
4. Открыть:
- Student cabinet: `http://127.0.0.1:5174/`
- Swagger: `http://127.0.0.1:8080/docs`

После `make up` учётка `student@easyitlab.tech / student123` создаётся автоматически при старте сервисов.

## Jenkins + Allure note
Если в job `training-github-allure` появляется ошибка `python3: command not found`, пересоберите Jenkins:
```bash
docker compose --env-file .env up -d --build jenkins
```

## Меню студента
В левом меню оставлены только:
- Dashboard
- Employees
- Clients
- Jenkins
- PostgreSQL
- REST API / Swagger
- Redis
- Kafka

## Проверка student flow
1. Логин `student@easyitlab.tech / student123`
2. Открыть `Employees` и нажать `Generate entities`
3. Открыть `Clients` и нажать `Generate entities`
4. Открыть `Jenkins`, `PostgreSQL`, `REST API / Swagger`, `Redis`, `Kafka`
5. Проверить переключение EN/RU
6. Проверить Logout
