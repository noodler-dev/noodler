django:
	uv run python manage.py runserver

celery:
	uv run celery -A noodler worker --loglevel=INFO

clean:
	uv run ruff format .
	uv run djlint . --reformat

lint:
	uv run ruff check .