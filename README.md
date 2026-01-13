# Noodler

[Noodler](http://noodler.dev/) is a feature rich platform for evaluating AI/LLM applications. 

## Docker Deployment

To run the entire application using Docker:

```bash
git clone https://github.com/noodler-dev/noodler.git
cd noodler

# Optionally copy and customize environment variables
cp .env.example .env

docker compose up -d
```

This will start:
- Django web server on `http://localhost:8000`
- Celery worker for background tasks
- RabbitMQ message broker (management UI at `http://localhost:15672`)

The database will be automatically migrated on first startup. The SQLite database and RabbitMQ data are persisted in Docker volumes.

### Environment Variables

You can customize the configuration by creating a `.env` file from `.env.example`:
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts (default: `*`)
- `RABBITMQ_USER`: RabbitMQ username (default: `guest`)
- `RABBITMQ_PASSWORD`: RabbitMQ password (default: `guest`)
- `CELERY_BROKER_URL`: Celery broker URL (default: `pyamqp://guest@localhost//` for local dev)

To stop all services:

```bash
docker compose down
```

To rebuild after code changes:

```bash
docker compose up -d --build
```

## Local Development

Install the Python dependencies, preferably using [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uv sync
```

### Celery

Make sure RabbitMQ is running:

```bash
sudo systemctl start rabbitmq-server
```

Then run Celery:

```bash
uv run celery -A noodler worker --loglevel=INFO
```