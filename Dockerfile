FROM python:3.12-slim
WORKDIR /app
# Stream logs immediately so Railway shows boot/seed output in real time.
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary
COPY . .
EXPOSE 8000
# boot.py seeds the 2025 season into the LIVE db on first start (if empty),
# then launches uvicorn. Seeding at runtime — not build time — is what makes
# the preload land in Postgres (DATABASE_URL) instead of a throwaway sqlite.
CMD ["python", "boot.py"]
