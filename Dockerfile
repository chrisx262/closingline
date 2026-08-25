FROM python:3.12-slim
WORKDIR /app
# Stream logs immediately so Railway shows boot/seed output in real time.
ENV PYTHONUNBUFFERED=1
# NOTE: loaders/circa_sheet.py needs tesseract-ocr + poppler-utils to read
# Circa's image-only contest PDFs, but that feature was shelved (no edge -- see
# docs/circa_line_value_backtest.md), so the server never reads one. Installing
# ~150MB of OCR tooling on every build for code that never runs is not worth
# it. If Circa work is ever revived, restore this line:
#   RUN apt-get update && apt-get install -y --no-install-recommends \
#       tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
# The parser still runs locally, where those tools are already installed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary
COPY . .
EXPOSE 8000
# boot.py seeds the 2025 season into the LIVE db on first start (if empty),
# then launches uvicorn. Seeding at runtime — not build time — is what makes
# the preload land in Postgres (DATABASE_URL) instead of a throwaway sqlite.
CMD ["python", "boot.py"]
