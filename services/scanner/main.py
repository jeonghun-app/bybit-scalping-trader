"""
Scanner Service 메인 진입점
"""
import sys
import os

# 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'managers'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'processors'))

from core.scanner_service_redis import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
