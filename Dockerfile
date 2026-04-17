# Use official Python slim image — small, fast, secure
FROM python:3.11-slim

# Install system dependencies needed for some Python packages
# (psycopg2 needs libpq, trafilatura may need some text tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first — Docker caches this layer so if only code changes,
# it doesn't reinstall all packages. This speeds up rebuilds significantly.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the code
COPY . .

# Railway sets $PORT automatically. Gunicorn binds to it.
# We don't EXPOSE a port here because Railway handles port routing.

# Default command — Railway will override this per service (web vs worker)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]
