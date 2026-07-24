FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY frontend/ ./frontend/
COPY sql/ ./sql/
COPY start.sh ./start.sh
RUN chmod +x start.sh

CMD ["./start.sh"]