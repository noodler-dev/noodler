# Noodler

Make sure rabbitmq is running:

```bash
sudo systemctl start rabbitmq-server
```

Then run Celery:

```bash
uv run celery -A noodler worker --loglevel=INFO
```