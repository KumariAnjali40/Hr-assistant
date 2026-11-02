FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd -m -u 1001 app && mkdir -p /data/uploads && chown -R app /data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app . .
USER app
EXPOSE 8000
# Migrations run on start for dev. In Kubernetes run `alembic upgrade head` as a Job instead.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
