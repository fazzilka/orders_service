# Orders Service (FastAPI)

Тестовое задание: асинхронный сервис заказов на FastAPI + PostgreSQL + Redis cache + RabbitMQ (event-bus) + Consumer + Celery worker.

## Стек

- Python 3.12+
- FastAPI (async)
- PostgreSQL + SQLAlchemy 2.0 async + Alembic
- Redis (async) — кеш заказов (TTL = 300s)
- RabbitMQ — event-bus (`new_order`)
- Consumer (отдельный сервис) читает RabbitMQ и вызывает Celery task
- Celery — фоновые задачи (broker/backend: Redis)
- JWT OAuth2 Password Flow (`/register/`, `/token/`)
- CORS (origins из env)
- Rate limiting по IP (slowapi) для `/token/` и `/orders/*`

## Быстрый старт (Docker)

1) Создать `.env`:

```bash
cp .env.example .env
```

2) Запуск:

```bash
docker compose up --build
```

- Swagger: `http://localhost:18000/docs`
- RabbitMQ UI: `http://localhost:18001` (логин/пароль из `.env`)

При старте `api` автоматически ждёт Postgres и выполняет миграции: `alembic upgrade head`.

## API примеры (curl)

### 1) Register

```bash
curl -s -X POST "http://localhost:18000/register/" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

### 2) Token (OAuth2 Password Flow)

```bash
TOKEN=$(curl -s -X POST "http://localhost:18000/token/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password123" | jq -r '.access_token')
echo "$TOKEN"
```

### 3) Create order (+ publish `new_order`)

```bash
ORDER=$(curl -s -X POST "http://localhost:18000/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"sku":"A1","qty":2},{"sku":"B2","qty":1}],"total_price":123.45}')
echo "$ORDER"
ORDER_ID=$(echo "$ORDER" | jq -r '.id')
USER_ID=$(echo "$ORDER" | jq -r '.user_id')
```

### 4) Get order (read-through cache: Redis -> Postgres -> Redis)

```bash
curl -s "http://localhost:18000/orders/$ORDER_ID/" \
  -H "Authorization: Bearer $TOKEN"
```

### 5) Update status (PATCH) + cache update

```bash
curl -s -X PATCH "http://localhost:18000/orders/$ORDER_ID/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"PAID"}'
```

### 6) List user orders (user_id must equal current_user.id, иначе 403)

```bash
curl -s "http://localhost:18000/orders/user/$USER_ID/" \
  -H "Authorization: Bearer $TOKEN"
```

## Проверка сценария “создал заказ -> событие -> consumer -> celery”

1) Создайте заказ (см. выше).
2) Посмотрите логи:

```bash
docker compose logs -f consumer celery-worker
```

Ожидаемые сообщения:
- consumer: `new_order received ...` и `Celery task queued ...`
- celery-worker: `Order <order_id> processed` (после ~2 секунд)

## Полезные команды (Makefile)

- `make run` — поднять сервисы в фоне
- `make logs` — смотреть логи
- `make down` — остановить и удалить volume'ы
- `make lint` — формат + линт (ruff)
- `make upgrade` — применить миграции (локально)
