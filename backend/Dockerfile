FROM python:3.12-slim

WORKDIR /app

# Rendszer függőségek
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python függőségek
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Forráskód
COPY . .

# Adatbázis könyvtár (volume-mountolt)
RUN mkdir -p /data

# Nem root felhasználó
RUN useradd -m appuser && chown -R appuser /app /data
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
