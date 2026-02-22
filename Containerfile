# Stage 1: Builder
# Use the official Python 3.13 slim image for a smaller base
FROM python:3.13-slim AS builder

# Copy the uv binary from the official uv container image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# Set environment variables for uv best practices
ENV UV_NO_DEV=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy project files
COPY . .

# Use uv to install dependencies with caching
# The cache mount dramatically speeds up rebuilds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Stage 2: Runtime
# Start from the same base image
FROM python:3.13-slim AS runtime

# Set the working directory
WORKDIR /app

# Copy the installed packages (and application code) from the builder stage
COPY --from=builder /app /app

ENV PATH="$PATH:/app/.venv/bin"

# Make port 5002 available to the world outside this container
EXPOSE 5002

# Run app.py when the container launches via gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "app:app"]