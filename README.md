# Demo Lab Chatbot Orchestrator 🚀

AI-powered chatbot orchestrator with RAG (Retrieval-Augmented Generation) and multi-worker architecture.

---

## 🚀 Quick Start

Choose your deployment:

- **[Development](#-local-development)** - Full stack in Docker with local services
- **[Production](#-production-deployment)** - Deploy with Azure services

---

## 🛠️ Local Development

Run everything in Docker with local RabbitMQ and Redis.

### Prerequisites

- Docker & Docker Compose
- Azure OpenAI API key
- Azure PostgreSQL database

### Setup

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd demo-lab-chatbot-orchestrator
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   nano .env
   ```
   
   Update All Credential Value

3. **Start all services**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

4. **Check status**
   ```bash
   docker-compose -f docker-compose.dev.yml ps
   ```

### Access Services

- **API Documentation**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Flower (Celery Monitor)**: http://localhost:5555

### View Logs

```bash
# All services
docker-compose -f docker-compose.dev.yml logs -f

# Specific service
docker-compose -f docker-compose.dev.yml logs -f fastapi
docker-compose -f docker-compose.dev.yml logs -f celery_worker_chat
```

### Stop Services

```bash
docker-compose -f docker-compose.dev.yml down
```

---

## ☁️ Production Deployment

Deploy with Azure RabbitMQ and Redis.

### Prerequisites

- Docker & Docker Compose
- Azure OpenAI subscription
- Azure PostgreSQL database
- Azure RabbitMQ instance
- Azure Redis Cache

### Setup

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd demo-lab-chatbot-orchestrator
   ```

2. **Configure environment**
   ```bash
   cp .env.production .env
   nano .env
   ```
   
   Update with production values

3. **Pre-create RabbitMQ queues** (required in production)
   
   Access RabbitMQ Management UI and create:
   
   **Exchanges:**
   - Name: `demo_labs`, Type: `topic`
   - Name: `default`, Type: `direct`
   
   **Queues:** (bind to `demo_labs` exchange)
   - `chat_incoming` → routing key: `chat.incoming`
   - `chat_outgoing` → routing key: `chat.outgoing`
   - `embedding.qna` → routing key: `embedding.qna`
   - `embedding.pdf` → routing key: `embedding.pdf`
   - `embedding.text_to_sql` → routing key: `embedding.text_to_sql`

4. **Deploy**
   ```bash
   docker-compose up -d --build
   ```

5. **Check status**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

### Scale Workers

```bash
# Scale chat workers
docker-compose up -d --scale celery_worker_chat=3

# Scale embedding workers
docker-compose up -d --scale celery_worker_embedding=2
docker-compose up -d --scale celery_worker_pdf=2
```

### Stop Services

```bash
docker-compose down
```

---

## 📝 Common Commands

### Development

```bash
# Start services
docker-compose -f docker-compose.dev.yml up -d

# Rebuild after code changes
docker-compose -f docker-compose.dev.yml up -d --build

# View logs
docker-compose -f docker-compose.dev.yml logs -f fastapi

# Stop services
docker-compose -f docker-compose.dev.yml down

# Remove volumes (clean start)
docker-compose -f docker-compose.dev.yml down -v
```

### Production

```bash
# Start services
docker-compose up -d

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f celery_worker_chat

# Restart specific service
docker-compose restart celery_worker_chat

# Stop services
docker-compose down
```

### Database Migrations

```bash
# Development
docker-compose -f docker-compose.dev.yml exec fastapi alembic upgrade head

# Production
docker-compose exec fastapi alembic upgrade head
```

### Worker Health Check

```bash
# Development
docker-compose -f docker-compose.dev.yml exec celery_worker_chat \
  celery -A app.workers.celery_app inspect active

# Production
docker-compose exec celery_worker_chat \
  celery -A app.workers.celery_app inspect active
```

---

## 🔌 API Usage

### Submit Chat Message

```bash
curl -X POST http://localhost:8000/api/v1/queue/submit \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "session_id": "session-001",
    "conversation_id": "conv-001",
    "persona_id": "persona-uuid",
    "dataset_id": "dataset-uuid",
    "message": "What is Python?",
    "timestamp": "2025-11-06T10:00:00Z"
  }'
```

### API Documentation

Visit http://localhost:8000/docs for interactive API documentation.

---

## 🐳 Docker Compose Files

| File | Purpose | Services |
|------|---------|----------|
| `docker-compose.dev.yml` | **Local development** | Redis, RabbitMQ, FastAPI, All Workers, Flower |
| `docker-compose.yml` | **Production** | FastAPI, Workers only (uses Azure Redis/RabbitMQ) |

---

## 🔧 Troubleshooting

### Development Issues

**Services won't start**
```bash
# Check logs
docker-compose -f docker-compose.dev.yml logs

# Restart services
docker-compose -f docker-compose.dev.yml restart
```

**Port already in use**
```bash
# Check what's using the port
lsof -i :8000
lsof -i :5672
lsof -i :6379

# Kill the process or change port in docker-compose.dev.yml
```

**Workers can't connect**
```bash
# Check if Redis and RabbitMQ are healthy
docker-compose -f docker-compose.dev.yml ps

# Check container logs
docker-compose -f docker-compose.dev.yml logs redis
docker-compose -f docker-compose.dev.yml logs rabbitmq
```

### Production Issues

**Queues not found**

Production requires manual queue creation. See step 3 in [Production Deployment](#-production-deployment).

**Workers can't connect to Azure**

```bash
# Verify environment variables
docker-compose exec fastapi env | grep -E "RABBITMQ|REDIS"

# Check connectivity
docker-compose exec fastapi ping your-azure-host
```

**Database connection failed**

```bash
# Test database connection
docker-compose exec fastapi python -c "
from app.db.session import SessionLocal
db = SessionLocal()
print('✓ Connected')
db.close()
"
```

---