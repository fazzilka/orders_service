# Orders Service — отчёт по проекту

Дата: 2026-02-07  
Папка проекта: `/home/fazzilka/PycharmProjects/orders_service`

Этот документ совмещает:
1) отчёт “что было сделано/исправлено” в ходе работ;  
2) краткое описание возможностей проекта;  
3) назначение каждого файла в репозитории (без учёта `.venv/` и `__pycache__/`).

---

## 1) Что умеет проект (возможности)

Проект — асинхронный сервис заказов на FastAPI со связкой PostgreSQL + Redis + RabbitMQ + Consumer + Celery.

Функциональность:
- **Пользователи**: регистрация, логин по паролю, выдача JWT.
- **JWT авторизация**:
  - `access` + `refresh` токены;
  - поддержка **Bearer** (`Authorization: Bearer ...`) и **HttpOnly cookies** (`user_access_token`/`user_refresh_token`);
  - refresh-токен не подходит для защищённых эндпоинтов (проверяется `typ`).
- **Заказы**:
  - создать заказ;
  - получить заказ по `id`;
  - обновить статус заказа (`PAID/SHIPPED/...`);
  - получить список заказов пользователя.
- **Redis cache**: read-through кеш заказа (TTL из env).
- **RabbitMQ event-bus**: при создании заказа публикуется событие `new_order`.
- **Consumer** (отдельный сервис): читает `new_order` из RabbitMQ и ставит задачу в Celery.
- **Celery worker**: обрабатывает задачу `process_order` (демо-обработка).
- **Rate limiting**: лимиты по IP на `/token/` и `/orders/*` (slowapi).
- **CORS**: origins берутся из env.
- **Healthcheck**: `GET /health/`.

---

## 2) Архитектура и потоки

### 2.1 Сервисы docker-compose

- `postgres` — основная БД (users/orders).
- `redis` — кеш заказов (DB 0) + rate limit storage (DB 1) + Celery broker/result backend (DB 2).
- `rabbitmq` — event-bus для `new_order` + Management UI.
- `api` — FastAPI приложение (Swagger, auth, orders).
- `consumer` — подписчик RabbitMQ, который ставит Celery задачи.
- `celery-worker` — воркер, выполняющий задачи.

### 2.2 Поток “создание заказа → событие → consumer → celery”

1) Клиент вызывает `POST /orders/`.
2) `api` пишет заказ в Postgres.
3) `api` кладёт заказ в Redis кеш и публикует `new_order` в RabbitMQ.
4) `consumer` получает событие и отправляет задачу `worker.tasks.process_order` в Celery (через Redis broker).
5) `celery-worker` выполняет задачу и пишет лог “Order <id> processed”.

---

## 3) Как запустить и попасть в Swagger

1) Подготовить env:

```bash
cp .env.example .env
```

2) Запуск:

```bash
make run
```

или:

```bash
docker compose up --build -d
```

3) Открыть:
- Swagger: `http://localhost:18000/docs` (порт задаётся `API_PORT`, по умолчанию `18000`)
- RabbitMQ UI: `http://localhost:18001` (порт задаётся `RABBITMQ_MANAGEMENT_PORT`, по умолчанию `18001`)

Полезно:
- Логи: `make logs`
- Остановить и удалить volume’ы: `make down`

---

## 4) Основные эндпоинты API

Auth:
- `POST /register/` — регистрация пользователя.
- `POST /token/` — OAuth2 Password Flow (form-data), возвращает `access_token`+`refresh_token` и выставляет cookies.
- `POST /token/refresh/` — обновляет пару токенов по refresh-cookie.
- `POST /logout/` — удаляет cookies.
- Совместимые алиасы (как в `Backend`): `POST /auth/user/login/`, `POST /auth/user/refresh/`, `POST /auth/user/logout/`.

Orders (все требуют access-токен пользователя):
- `POST /orders/` — создать заказ (+ publish `new_order`).
- `GET /orders/{order_id}/` — получить заказ (Redis → Postgres → Redis).
- `PATCH /orders/{order_id}/` — обновить статус заказа (+ обновление кеша).
- `GET /orders/user/{user_id}/` — список заказов пользователя (только для самого себя, иначе 403).

Health:
- `GET /health/` — простой статус.

---

## 5) Конфигурация через `.env` (ключевые переменные)

Смотреть полный список: `.env.example`.

Критичные:
- Порты на хосте:
  - `API_PORT` (Swagger будет на `http://localhost:${API_PORT}/docs`)
  - `RABBITMQ_MANAGEMENT_PORT` (UI RabbitMQ на `http://localhost:${RABBITMQ_MANAGEMENT_PORT}`)
- Postgres:
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
  - `DATABASE_URL` (asyncpg)
  - `POSTGRES_WAIT_TIMEOUT` (ожидание БД при старте)
- Redis: `REDIS_URL`
- RabbitMQ:
  - `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`, `RABBITMQ_URL`
  - `RABBIT_EXCHANGE`, `RABBIT_QUEUE`, `RABBIT_ROUTING_KEY`
- JWT:
  - `JWT_SECRET_KEY`, `JWT_ALGORITHM`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`
  - `REFRESH_TOKEN_EXPIRE_DAYS`
- CORS: `CORS_ORIGINS` (список или CSV)
- Rate limit:
  - `RATE_LIMIT_STORAGE_URI`, `RATE_LIMIT_TOKEN`, `RATE_LIMIT_ORDERS`
- Celery:
  - `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- Cache:
  - `CACHE_TTL_SECONDS`

---

## 6) Что требовалось и что сделано в ходе работ

### 6.1 Перевести порты на свободные

Сделано:
- `docker-compose.yml`: публикации портов вынесены в env-переменные:
  - API: `${API_PORT:-8000}:8000`
  - RabbitMQ UI: `${RABBITMQ_MANAGEMENT_PORT:-15672}:15672`
- `.env` / `.env.example`: добавлены дефолты `API_PORT=18000`, `RABBITMQ_MANAGEMENT_PORT=18001`
- `README.md`: обновлены ссылки на Swagger и RabbitMQ UI.

### 6.2 Починить падение миграций Alembic (ENUM)

Проблема: `DuplicateObjectError: type "order_status" already exists` при `alembic upgrade head`.

Сделано:
- `alembic/versions/0001_initial.py`: ENUM переведён на `postgresql.ENUM(..., create_type=False)` + явное `create(..., checkfirst=True)`.

### 6.3 Перенести/адаптировать auth user-токенов из проекта `Backend`

Сделано:
- Добавлены **access+refresh** токены с `typ`/`role`/`email` claims.
- Добавлены HttpOnly cookies для web-сценария.
- `get_current_user` принимает access-токен из Bearer или cookie и проверяет, что это именно access (`typ=access`, `role=user`).
- Добавлены refresh/logout эндпоинты и совместимые алиасы `/auth/user/*`.

### 6.4 Исправить хеширование паролей (bcrypt/passlib)

Сделано:
- Перешли на `bcrypt` напрямую и добавили pre-hash `sha256(password)` перед bcrypt.
- `verify_password()` оставляет обратную совместимость: пробует raw-bcrypt, затем sha256+bcrypt.

### 6.5 Изменённые/добавленные файлы в рамках работ

- `docker-compose.yml`
- `.env`
- `.env.example`
- `README.md`
- `alembic/versions/0001_initial.py`
- `app/core/config.py`
- `app/core/security.py`
- `app/core/auth_cookies.py` (новый)
- `app/api/v1/auth.py`
- `app/api/deps.py`
- `app/schemas/auth.py`

---

## 7) Структура репозитория: файлы и ответственность

Ниже перечислены **все** файлы проекта (кроме артефактов окружения `.venv/` и `__pycache__/`).

### 7.1 Корень проекта

- `README.md` — описание проекта, стек, быстрый старт, примеры curl.
- `ORDERS_SERVICE_REPORT.md` — этот отчёт.
- `docker-compose.yml` — Docker Compose конфигурация сервисов (api/postgres/redis/rabbitmq/consumer/celery-worker) и публикация хостовых портов через env.
- `Dockerfile` — сборка образа приложения (используется для `api`, `consumer`, `celery-worker`).
- `.dockerignore` — исключения для Docker build context.
- `.env` — локальная конфигурация (не коммитить секреты).
- `.env.example` — шаблон env с дефолтами и комментариями.
- `Makefile` — удобные команды: `run/logs/down/lint/upgrade`.
- `pyproject.toml` — зависимости/настройки (uv/ruff и т.п.).
- `uv.lock` — lockfile зависимостей для `uv`.
- `alembic.ini` — конфиг Alembic.
- `.gitignore` — игнорируемые файлы (если репозиторий подключён к git).

### 7.2 `alembic/`

- `alembic/env.py` — окружение Alembic: подхватывает `DATABASE_URL`, подключает metadata моделей и запускает миграции (async).
- `alembic/versions/0001_initial.py` — первичная схема БД (users/orders + ENUM `order_status`).

### 7.3 `scripts/`

- `scripts/wait_for_postgres.py` — ожидание Postgres перед миграциями/стартом API (используется в `docker-compose.yml`).

### 7.4 `app/` (FastAPI приложение)

- `app/__init__.py` — маркер пакета.
- `app/main.py` — создание FastAPI приложения, подключение роутеров, startup/shutdown через lifespan (Redis + Rabbit).

#### 7.4.1 `app/api/`

- `app/api/__init__.py` — маркер пакета.
- `app/api/deps.py` — зависимости FastAPI:
  - `get_db()` — async SQLAlchemy session,
  - `get_redis()` — Redis из `app.state`,
  - `get_rabbit_exchange()` — Exchange из `app.state`,
  - `get_current_user()` — авторизация по Bearer или cookie.

#### 7.4.2 `app/api/v1/`

- `app/api/v1/__init__.py` — маркер пакета.
- `app/api/v1/auth.py` — эндпоинты регистрации/логина/refresh/logout.
- `app/api/v1/orders.py` — эндпоинты заказов, кеш и публикация событий.

#### 7.4.3 `app/core/`

- `app/core/__init__.py` — маркер пакета.
- `app/core/config.py` — Pydantic Settings (чтение `.env`, все настройки проекта).
- `app/core/logging.py` — базовая настройка логирования.
- `app/core/cors.py` — подключение CORS middleware из env `CORS_ORIGINS`.
- `app/core/rate_limit.py` — настройка slowapi limiter/middleware.
- `app/core/security.py` — безопасность:
  - хеширование/проверка пароля (`bcrypt` + `sha256` prehash),
  - JWT provider (`encode/decode`),
  - `UserTokenService` (access/refresh, проверки `typ/role`).
- `app/core/auth_cookies.py` — установка/очистка HttpOnly cookies с user access/refresh токенами.

#### 7.4.4 `app/db/`

- `app/db/__init__.py` — маркер пакета.
- `app/db/base.py` — базовый класс `Base` для SQLAlchemy моделей.
- `app/db/session.py` — создание async engine и `async_session_maker`.

##### 7.4.4.1 `app/db/models/`

- `app/db/models/__init__.py` — импорт моделей (чтобы Alembic видел metadata).
- `app/db/models/user.py` — модель `User` (email/password hash, отношения).
- `app/db/models/order.py` — модель `Order` + enum `OrderStatus`.

#### 7.4.5 `app/integrations/`

- `app/integrations/__init__.py` — маркер пакета.
- `app/integrations/redis.py` — подключение/проверка Redis с retry + корректное закрытие клиента.
- `app/integrations/rabbit.py` — подключение RabbitMQ с retry + объявление exchange.

#### 7.4.6 `app/schemas/` (Pydantic схемы)

- `app/schemas/__init__.py` — маркер пакета.
- `app/schemas/auth.py` — схемы для auth: `UserCreate`, `UserRead`, `TokenPair`, и т.д.
- `app/schemas/order.py` — схемы для заказов: create/update/read.

#### 7.4.7 `app/services/` (бизнес-логика)

- `app/services/__init__.py` — маркер пакета.
- `app/services/users.py` — работа с пользователями (CRUD/authenticate).
- `app/services/orders.py` — операции с заказами (create/get/list/update).
- `app/services/cache.py` — кеширование заказа в Redis (get/set/invalidate).
- `app/services/events.py` — публикация `new_order` в RabbitMQ.

### 7.5 `consumer/` (RabbitMQ consumer)

- `consumer/__init__.py` — маркер пакета.
- `consumer/main.py` — подписка на очередь RabbitMQ и постановка задачи в Celery.

### 7.6 `worker/` (Celery worker)

- `worker/__init__.py` — маркер пакета.
- `worker/celery_app.py` — конфигурация Celery (broker/backend из env).
- `worker/tasks.py` — задача `process_order` (демо-обработка заказа).

---

## 8) Известные предупреждения/заметки

- Celery предупреждает про запуск под root в контейнере — функционально не мешает, но лучше запускать под отдельным пользователем.
- Redis может предупреждать про `vm.overcommit_memory` — для dev обычно терпимо, для production лучше настроить.

---

## 9) Где лежит отчёт

Исходный файл отчёта в проекте: `ORDERS_SERVICE_REPORT.md`.

Если нужно положить копию в “Документы”:

```bash
cp /home/fazzilka/PycharmProjects/orders_service/ORDERS_SERVICE_REPORT.md "/home/fazzilka/Документы/ORDERS_SERVICE_REPORT.md"
```
