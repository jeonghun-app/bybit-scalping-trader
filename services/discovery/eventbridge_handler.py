import json
import boto3
from discovery_service_redis import DiscoveryService

def lambda_handler(event, context):
    """EventBridge에서 호출되는 Discovery 핸들러"""
    
    discovery = DiscoveryService()
    
    try:
        # Discovery 실행
        result = discovery.run_discovery()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Discovery completed successfully',
                'result': result
            })
        }
    except Exception as e:
        print(f"Discovery failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Discovery failed',
                'error': str(e)
            })
        }
