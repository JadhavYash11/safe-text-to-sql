FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY frontend ./frontend
COPY .env.example ./
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data

EXPOSE 8000 8501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
