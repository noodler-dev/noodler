# Noodler

[Noodler](http://noodler.dev/) is a feature rich platform for evaluating AI/LLM applications. 

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