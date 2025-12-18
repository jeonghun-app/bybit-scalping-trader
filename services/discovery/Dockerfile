FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Discovery 전용 requirements 복사 및 설치
COPY services/discovery/requirements-discovery.txt .
RUN pip install --no-cache-dir -r requirements-discovery.txt

# Discovery 서비스 복사
COPY services/discovery/ .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Discovery 서비스 실행 (Redis 버전)
CMD ["python", "discovery_service_redis.py"]
