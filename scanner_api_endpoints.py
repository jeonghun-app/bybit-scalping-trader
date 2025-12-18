"""
Scanner V2 모니터링 API 엔드포인트
로컬 백엔드에 추가할 API 함수들
"""
import json
import subprocess
import re
from datetime import datetime, timedelta

def get_scanner_status():
    """Scanner 서비스 상태 조회"""
    try:
        cmd = [
            'aws', 'ecs', 'describe-services',
            '--cluster', 'crypto-backtest-cluster', 
            '--services', 'crypto-backtest-scanner-v2',
            '--query', 'services[0].{Name:serviceName,Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}',
            '--output', 'json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except:
        return None

def get_scanner_logs(minutes=5):
    """Scanner 최근 로그 조회"""
    try:
        since_time = datetime.now() - timedelta(minutes=minutes)
        since_str = f"{int(since_time.timestamp())}000"
        
        cmd = [
            'aws', 'logs', 'filter-log-events',
            '--log-group-name', '/ecs/crypto-backtest-scanner-v2',
            '--start-time', since_str,
            '--max-items', '30',
            '--output', 'json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_data = json.loads(result.stdout)
            events = log_data.get('events', [])
            
            parsed_logs = []
            for event in events[-20:]:
                message = event.get('message', '')
                timestamp = datetime.fromtimestamp(event.get('timestamp', 0) / 1000)
                
                level = 'info'
                if 'ERROR' in message or '❌' in message:
                    level = 'error'
                elif 'WARNING' in message or '⚠️' in message:
                    level = 'warning'
                elif '✅' in message:
                    level = 'success'
                
                parsed_logs.append({
                    'timestamp': timestamp.isoformat(),
                    'message': message.strip(),
                    'level': level
                })
            
            return parsed_logs
        return []
    except:
        return []

def get_opportunities_count():
    """발행된 기회 신호 개수 조회"""
    try:
        since_time = datetime.now() - timedelta(hours=1)
        since_str = f"{int(since_time.timestamp())}000"
        
        cmd = [
            'aws', 'logs', 'filter-log-events',
            '--log-group-name', '/ecs/crypto-backtest-scanner-v2',
            '--start-time', since_str,
            '--filter-pattern', '기회',
            '--max-items', '50',
            '--output', 'json'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_data = json.loads(result.stdout)
            events = log_data.get('events', [])
            
            total = 0
            for event in events:
                message = event.get('message', '')
                match = re.search(r'발행 기회: (\d+)', message)
                if match:
                    total += int(match.group(1))
            
            return total
        return 0
    except:
        return 0

# Flask 라우트 예시 (기존 백엔드에 추가)
"""
from flask import jsonify

@app.route('/api/scanner/status')
def api_scanner_status():
    data = get_scanner_status()
    return jsonify({'success': True, 'data': data}) if data else jsonify({'success': False})

@app.route('/api/scanner/logs')
def api_scanner_logs():
    logs = get_scanner_logs()
    return jsonify({'success': True, 'data': logs})

@app.route('/api/scanner/opportunities')
def api_scanner_opportunities():
    count = get_opportunities_count()
    return jsonify({'success': True, 'data': {'total': count}})
"""
