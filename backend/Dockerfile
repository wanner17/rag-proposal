FROM python:3.11-slim

# LibreOffice (HWP → PDF 변환용) + SVN
RUN apt-get update && apt-get install -y \
    libreoffice \
    subversion \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY plugins/ ./plugins/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
