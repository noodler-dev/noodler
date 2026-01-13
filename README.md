# Noodler

[Noodler](http://noodler.dev/) is a feature rich platform for evaluating AI/LLM applications. 

## Self-Hosting

To run the entire application using Docker:

```bash
git clone https://github.com/noodler-dev/noodler.git
cd noodler

docker compose up -d
```

You should now be able to visit [http://localhost:8000/accounts/login](http://localhost:8000/accounts/login`)

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