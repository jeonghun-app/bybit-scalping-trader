FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# AWS SDK 및 메시지 큐 라이브러리 설치
RUN pip install --no-cache-dir \
    boto3==1.34.* \
    pika==1.3.*

# 공통 라이브러리 복사
COPY src/ ./src/
COPY config/ ./config/

# Scanner 서비스 코드 복사
COPY services/scanner/scanner_service.py .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV AWS_DEFAULT_REGION=ap-northeast-2

# Scanner 서비스 실행
CMD ["python", "scanner_service.py"]
