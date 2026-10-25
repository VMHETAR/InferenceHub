# InferenceHub — ML Model Serving Platform

**Teaching artifact** for FastAPI, PostgreSQL, Redis, Celery, and AWS.
Every file explains the *concept* behind the code, not just the syntax.

---

## What this is (one paragraph)

InferenceHub is a production-grade ML model serving platform. You register a model, upload an artifact, and call `/predict`. Behind that endpoint: JWT auth, rate-limiting via Redis sorted sets, a cache-aside layer, an ONNX inference engine, Celery async workers (stats, drift detection, cleanup), partitioned PostgreSQL logs, and a full AWS Terraform stack (VPC, RDS, ElastiCache, ECS Fargate, S3, Lambda, API Gateway, CloudWatch).

This repo is intentionally a **learning vehicle** — not a minimal demo. Read `docs/LEARNING_PATH.md` for the order.

---

## Quick start

```bash
# 1. Local stack (FastAPI + Postgres + Redis + Celery worker + Celery beat)
docker compose up

# 2. Or build the image directly
docker build -t inferencehub .
docker run -p 8000:8000 inferencehub

# 3. OpenAPI docs (auto-generated from Pydantic schemas)
curl http://localhost:8000/docs
```

---

## Project structure (what each directory is *for*)

```
.
├── app/                     # FastAPI app + services + engine + workers
│   ├── main.py              # App factory (create_app) + lifespan + middleware + routers
│   ├── config.py            # Pydantic Settings (env-based, 12-factor)
│   ├── dependencies.py      # DI: DB session, current user, rate limiter
│   ├── database.py          # Async SQLAlchemy engine + session factory + base
│   ├── redis_client.py      # Redis pool + helpers
│   ├── api/                 # Routes grouped by domain (auth, users, models, versions, inference, ws, monitoring)
│   ├── schemas/             # Pydantic contracts (separate from ORM models — explain why)
│   ├── models/              # SQLAlchemy ORM (UUID PKs, JSONB, partitioned logs, GIN indexes)
│   ├── services/            # Business logic (auth, model, version, inference, cache, rate limit)
│   ├── inference_engine/    # Loader (S3 → temp → ONNX), LRU memory cache, predictor (numpy → ONNX → timing), schema validator
│   └── workers/             # Celery: app config, tasks (daily stats, drift, cleanup), beat schedules
├── alembic/                 # DB migrations (auto + hand-tuned)
├── docs/                    # 7 teaching docs (ARCHITECTURE, DATABASE, REDIS, AWS, DEPLOYMENT, API, LEARNING_PATH)
├── tests/                   # pytest-asyncio + fakeredis + testcontainers fixtures
├── scripts/                 # seed_db, generate_sample_model, load_test (Locust)
├── terraform/               # AWS IaC (vpc, rds, elasticache, ecs, s3, api_gateway, lambda, cloudwatch modules)
├── inferencehub/            # Source package (Dockerfile, README, alembic, scripts, terraform, docs, tests, app/)
├── main.py                  # Minimal entry-point (FastAPI instance — overridden by inferencehub/app/main.py in production)
├── docker-compose.yml       # Local dev: FastAPI + Postgres 15 + Redis 7 + Celery worker (depends on db + redis)
└── README.md                # This file
```

---

## Important design decisions (the *why* — read these first)

| Decision | Where documented | Key reason |
|---|---|---|
| FastAPI app factory (`create_app()` + lifespan) | `app/main.py` | Lets you build different configs for test vs prod; startup/shutdown handles DB + Redis + warm cache |
| UUID primary keys (not auto-increment) | `app/models/` | Needed for distributed systems / sharding (no central coordinator for integers) |
| SQLAlchemy 2.0 async (`Mapped`, `mapped_column`) | `app/database.py` | Non-blocking DB I/O — one worker handles more concurrent requests |
| Pydantic schemas separate from ORM models | `app/schemas/` | API contract ≠ DB layer; allows versioning the API without migrating DB |
| JWT (short 15m access + 7d refresh + rotation) | `app/services/auth_service.py` | Short access limits theft window; rotation prevents replay of stolen refresh tokens |
| API keys as alt auth for `/predict` | `app/services/auth_service.py` | JWT is user-centric; API keys are service-to-service (machine calling endpoint) |
| `bcrypt` with `rounds=12` | `app/services/auth_service.py` | Embedded salt per password; 2^12 iterations make brute-force months not minutes |
| Redis sorted sets for sliding-window rate limit | `app/services/rate_limiter.py` | Accurate at window boundaries (INCR/EXPIRE is approximate); pipeline reduces round trips |
| Cache-aside (not write-through/behind) | `app/services/cache_service.py` | Correct for read-heavy model metadata; TTL + explicit invalidation defense-in-depth |
| Thundering-herd protection (`SETNX` lock) | `app/services/cache_service.py` | Prevents all instances hitting DB when cache expires at same time |
| ONNX Runtime as interchange format | `app/inference_engine/loader.py` | Framework-agnostic; optimized runtime; avoids loading whole framework into memory |
| LRU in-memory model cache + Redis pubsub | `app/inference_engine/model_cache.py` | In-process = nanoseconds; Redis = cross-instance consistency; pubsub invalidates all nodes |
| `time.perf_counter_ns()` for latency | `app/inference_engine/predictor.py` | Monotonic, nanosecond resolution; not affected by system clock changes |
| PostgreSQL partitioned `inference_log` by month | `app/models/inference_log.py` | Aggregating millions of rows on every dashboard load is expensive; partition pruning speeds queries |
| GIN index on `input_schema` (JSONB) | `app/models/model_version.py` | Enables fast JSONB queries without full-table scan |
| Partial index `api_keys WHERE revoked_at IS NULL` | `app/models/api_key.py` | Only index active keys — smaller index, faster reads |
| Composite index `(model_id, created_at)` on logs | `app/models/inference_log.py` | Speeds time-range queries per model |
| Celery broker = Redis (not RabbitMQ) | `app/workers/celery_app.py` | Simpler, sufficient for most workloads; RabbitMQ adds ack/routing needed only at scale |
| WebSocket (not SSE / long-poll) for batch | `app/api/ws.py` | Bidirectional stream; server sends each result as it completes |
| Cursor-based pagination (not offset) | `app/api/*.py` | Offset slows at large pages (DB still scans skipped rows); cursor uses indexed column |
| Multi-stage Docker build (build + runtime) | `inferencehub/Dockerfile` | Smaller final image (~only site-packages + code, not build tools) |

---

## Tech stack (with *why* for each)

- **FastAPI** — async Python web framework with automatic OpenAPI docs from type hints
- **PostgreSQL 15** — relational, JSONB, native partitioning, GIN indexes, ACID
- **Redis 7** — single-threaded (no locks needed), in-memory, pubsub, sorted sets
- **Celery + Redis broker** — async task queue for stats/drift/cleanup (decouples producer from consumer)
- **ONNX Runtime** — framework-independent ML runtime (sklearn → ONNX → predict)
- **AWS (Terraform)** — VPC, RDS (Postgres multi-AZ), ElastiCache (Redis), ECS Fargate, S3 (versioned artifacts), Lambda (S3-triggered validation), API Gateway (throttle + analytics + WAF), CloudWatch (structured logs + dashboards + alarms)
- **Pydantic + SQLAlchemy 2.0** — type-safe validation + async ORM with `Mapped`/`mapped_column`
- **Docker Compose + multi-stage Dockerfile** — reproducible local/dev/prod environments

---

## Commands

| Command | Description |
|---|---|
| `docker compose up` | Start full local stack |
| `docker build -t inferencehub .` | Build production image |
| `pytest` | Run all tests (async fixtures + fakeredis) |
| `pytest -x -q` | Quick fail-fast |
| `celery -A app.workers.celery_app.celery_app worker --loglevel=info` | Start Celery worker |
| `celery -A app.workers.celery_app.celery_app beat --loglevel=info` | Start Celery beat (scheduled tasks) |
| `terraform init && terraform plan` | Inspect AWS infrastructure |
| `uvicorn app.main:app --host 0.0.0.0 --port 8000` | Direct run (dev only) |

---

## Architecture overview (what a `/predict` request actually does)

1. **API Gateway** → routes + WAF + usage analytics + SSL
2. **ALB** (Application Load Balancer) → distributes to Fargate tasks
3. **FastAPI** `/predict` → auth (JWT or API key) → rate limiter (Redis sorted set) → cache check (Redis `model:{id}:meta`)
4. **Cache miss** → query Postgres → serialize → `SET` Redis TTL 300s → `DEL` on invalidation
5. **Model load** (if not in LRU memory cache) → download from S3 → load ONNX session → warm
6. **Prediction** → validate payload against JSON schema → numpy → ONNX `InferenceSession.run()` → `perf_counter_ns()` timing
7. **Log** → insert to partitioned `inference_log` → `compute_daily_stats` Celery task aggregates midnight
8. **Response** → JSON with latency, model version, prediction

See `docs/ARCHITECTURE.md` for the Mermaid diagram.

---

## Key docs (read in this order for learning)

1. `docs/ARCHITECTURE.md` — Mermaid diagram + component responsibilities + request flow
2. `docs/DATABASE.md` — Schema (ER diagram), indexing strategy, partitioning, connection pooling
3. `docs/REDIS.md` — Three roles (cache, rate limit, Celery broker), data structures, persistence (RDB vs AOF)
4. `docs/AWS.md` — Every service with "what it does / why here / self-managed alternative / cost / IAM"
5. `docs/DEPLOYMENT.md` — Local → ECR → Terraform apply → Alembic migrate → verify
6. `docs/API.md` — Endpoints + pagination + status codes + OpenAPI
7. `docs/LEARNING_PATH.md` — Week-by-week reading order + exercises (add forgot-password, OAuth2, admin roles, etc.)

---

## Testing philosophy

- Fixtures in `tests/conftest.py`: test Postgres DB, `fakeredis.aioredis` (no real Redis needed for unit tests — explains why), `test_client`, authenticated user, sample model/version
- Coverage targets: auth (register/login/refresh/expired), model CRUD + ownership isolation, version upload/status, inference (valid/invalid/model-not-found/rate-limit), cache (miss→hit/invalidate/TTL), rate limiter (under/at/window-slide), workers (Celery with mocked dependencies)

---

## Terraform modules (AWS infrastructure as code)

`terraform/modules/`: vpc, rds, elasticache, ecs, s3, api_gateway, lambda, cloudwatch
- **VPC** — 2 public + 2 private subnets across 2 AZs; NAT Gateway for private internet
- **RDS** — PostgreSQL 15 `db.t3.medium`; multi-AZ (synchronous standby in other AZ); 7-day backup
- **ElastiCache** — Redis 7.x `cache.t3.micro`; cluster mode disabled (explain when to enable)
- **ECS** — Fargate service + ALB + auto-scaling on CPU + env vars from SSM
- **S3** — Model artifacts + versioning + 90-day Glacier lifecycle + bucket policy (ECS task role only)
- **Lambda** — S3 PUT trigger → validate ONNX → update DB status (explain cold starts + mitigation)
- **API Gateway** — REST API + usage plans + throttling (explain why even with FastAPI routing: WAF, analytics, SSL, caching)
- **CloudWatch** — Log group + dashboard (p50/p95/p99 latency, error rate, request count) + alarm (>5% error for 5 min → SNS)
- **IAM** — Least-privilege per service (ECS: S3+RDS+ElastiCache+logs; Lambda: S3+RDS proxy)

---

## Design philosophy (why this reads like a textbook, not a tutorial)

- Every module docstring says **what** + **how it fits** + **key concept demonstrated**
- Inline comments explain **which alternative was rejected** (e.g., why sorted sets over INCR/EXPIRE, why cache-aside over write-through)
- Function docstrings say not just what, but **why it exists as a separate function** and what breaks without it (e.g., `bcrypt` salt embedding, refresh rotation prevents replay)
- No TODO placeholders — every file is complete; missing pieces are noted here (see "Not yet implemented")

---

## Not yet implemented (scaffold only — most modules empty)

Only these files contain real content today:
- `main.py` — minimal FastAPI
- `app/config.py` — Pydantic Settings
- `docker-compose.yml` — local stack definition
- `inferencehub/Dockerfile` — multi-stage build
- `inferencehub/README.md` — 2-line design note

Everything else exists as directory scaffold only (empty `app/api/`, `app/models/`, `docs/`, `tests/`, `terraform/modules/*`). The build prompt (stored in session `.jsonl`) defines the full target architecture; this README captures what's important from the existing files and the intended design.

---
