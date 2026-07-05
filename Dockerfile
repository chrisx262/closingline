FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary
COPY . .
# Load the real completed season at build so the board isn't empty on day one.
RUN python loaders/nflverse_loader.py 2025 || true
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
