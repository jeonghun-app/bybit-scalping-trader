FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Scanner 전용 requirements 복사 및 설치
COPY services/scanner/requirements-scanner.txt .
RUN pip install --no-cache-dir -r requirements-scanner.txt

# Scanner 서비스 전체 복사
COPY services/scanner/ .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Scanner 서비스 실행 (Redis 버전)
CMD ["python", "main.py"]
