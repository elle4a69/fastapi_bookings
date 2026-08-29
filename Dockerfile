FROM python:3.11-slim

WORKDIR /app

# Copy application code and dependencies
COPY ./app /app/app
COPY requirements.txt /app/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]