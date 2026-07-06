FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Copy the backend code
COPY ai/ /app/ai/

# Install dependencies using the pyproject.toml
# The pyproject.toml looks in ".." for the "ai" package, which resolves correctly here.
RUN pip install --no-cache-dir ./ai

# Expose the Cloud Run port
EXPOSE 8080

# Command to run the FastAPI server
CMD ["uvicorn", "ai.api.server:app", "--host", "0.0.0.0", "--port", "8080"]
