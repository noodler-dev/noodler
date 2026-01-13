FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv via pip
RUN pip install --no-cache-dir uv

# Verify uv is installed
RUN uv --version

# Copy project files for dependency installation
COPY pyproject.toml uv.lock* ./

# Install Python dependencies using uv
RUN uv sync --frozen || uv sync

# Copy remaining project files
COPY . .

# Collect static files (if needed)
RUN uv run python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]
