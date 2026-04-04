# API

## Base URL

- Local: `http://127.0.0.1:8080`
- Cloud example: `https://api.bank.easyitlab.tech`

## Authentication

Login endpoint:

```http
POST /auth/login
Content-Type: application/json
```

Request body:

```json
{
  "email": "student@easyitlab.tech",
  "password": "student123"
}
```

Use returned `access_token` as Bearer token:

```http
Authorization: Bearer <access_token>
```

## Main Student Areas

- `/students/dashboard`
- `/students/employees`
- `/students/clients`
- `/students/jenkins/job/runs`
