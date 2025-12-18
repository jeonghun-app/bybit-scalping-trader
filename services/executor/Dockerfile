FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY services/executor/requirements-executor.txt .
RUN pip install --no-cache-dir -r requirements-executor.txt

# Executor 서비스 전체 복사
COPY services/executor/ .

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 실행
CMD ["python3", "executor_service.py"]
