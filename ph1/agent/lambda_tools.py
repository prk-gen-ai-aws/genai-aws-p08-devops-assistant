"""
P08 DevOps Intelligence Assistant — Lambda Tools
3 tool groups: monitor, cost, alert
Single Lambda function with action routing
"""
import json
import boto3
import os
from datetime import datetime, timezone, timedelta

AWS_REGION    = os.environ.get('AWS_REGION', 'us-east-1')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')

logs_client  = boto3.client('logs', region_name=AWS_REGION)
cw_client    = boto3.client('cloudwatch', region_name=AWS_REGION)
ce_client    = boto3.client('ce', region_name=AWS_REGION)
sns_client   = boto3.client('sns', region_name=AWS_REGION)
lambda_client = boto3.client('lambda', region_name=AWS_REGION)


# ── Monitor Tools ─────────────────────────────────────────────

def get_cloudwatch_logs(log_group_name: str, hours: int = 1, filter_pattern: str = ''):
    """Get recent CloudWatch logs from a log group."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    kwargs = {
        'logGroupName': log_group_name,
        'startTime': int(start_time.timestamp() * 1000),
        'endTime': int(end_time.timestamp() * 1000),
        'limit': 20
    }
    if filter_pattern:
        kwargs['filterPattern'] = filter_pattern

    try:
        response = logs_client.filter_log_events(**kwargs)
        events = response.get('events', [])
        return {
            'log_group': log_group_name,
            'hours_searched': hours,
            'event_count': len(events),
            'events': [
                {
                    'timestamp': datetime.fromtimestamp(e['timestamp']/1000, tz=timezone.utc).isoformat(),
                    'message': e['message'].strip()
                }
                for e in events
            ]
        }
    except Exception as e:
        return {'error': str(e), 'log_group': log_group_name}


def get_lambda_errors(function_name: str, hours: int = 1):
    """Get recent errors from a Lambda function's CloudWatch logs."""
    log_group = f'/aws/lambda/{function_name}'
    result = get_cloudwatch_logs(
        log_group_name=log_group,
        hours=hours,
        filter_pattern='ERROR'
    )
    result['function_name'] = function_name
    return result


def get_metric_stats(namespace: str, metric_name: str,
                     dimension_name: str, dimension_value: str,
                     hours: int = 1):
    """Get CloudWatch metric statistics."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    try:
        response = cw_client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=[{'Name': dimension_name, 'Value': dimension_value}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Sum', 'Average', 'Maximum']
        )
        datapoints = sorted(response.get('Datapoints', []), key=lambda x: x['Timestamp'])
        return {
            'namespace': namespace,
            'metric': metric_name,
            'dimension': f'{dimension_name}={dimension_value}',
            'hours': hours,
            'datapoints': [
                {
                    'timestamp': dp['Timestamp'].isoformat(),
                    'sum': dp.get('Sum', 0),
                    'average': dp.get('Average', 0),
                    'maximum': dp.get('Maximum', 0)
                }
                for dp in datapoints
            ]
        }
    except Exception as e:
        return {'error': str(e)}


def list_lambda_functions():
    """List all Lambda functions in the account."""
    try:
        response = lambda_client.list_functions()
        functions = response.get('Functions', [])
        return {
            'count': len(functions),
            'functions': [
                {
                    'name': f['FunctionName'],
                    'runtime': f.get('Runtime', 'N/A'),
                    'last_modified': f.get('LastModified', 'N/A'),
                    'memory': f.get('MemorySize', 128),
                    'timeout': f.get('Timeout', 3)
                }
                for f in functions
            ]
        }
    except Exception as e:
        return {'error': str(e)}


# ── Cost Tools ────────────────────────────────────────────────

def get_cost_summary(days: int = 30):
    """Get AWS cost summary for the last N days."""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost']
        )
        results = response.get('ResultsByTime', [])
        total = sum(
            float(r['Total']['UnblendedCost']['Amount'])
            for r in results
        )
        return {
            'period_days': days,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'total_cost_usd': round(total, 4),
            'currency': 'USD'
        }
    except Exception as e:
        return {'error': str(e)}


def get_service_breakdown(days: int = 30):
    """Get AWS cost breakdown by service for the last N days."""
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )
        results = response.get('ResultsByTime', [])
        services = {}
        for period in results:
            for group in period.get('Groups', []):
                service = group['Keys'][0]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                services[service] = services.get(service, 0) + cost

        # Sort by cost descending, filter out zero-cost services
        sorted_services = sorted(
            [(k, round(v, 4)) for k, v in services.items() if v > 0],
            key=lambda x: x[1],
            reverse=True
        )
        return {
            'period_days': days,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'services': [
                {'service': s, 'cost_usd': c}
                for s, c in sorted_services
            ]
        }
    except Exception as e:
        return {'error': str(e)}


# ── Alert Tools ───────────────────────────────────────────────

def send_alert(subject: str, message: str, severity: str = 'INFO'):
    """Send an alert via SNS."""
    if not SNS_TOPIC_ARN:
        return {'error': 'SNS_TOPIC_ARN not configured'}

    full_message = f"[{severity}] {message}\n\nSent by P08 DevOps Intelligence Assistant"
    full_subject = f"[DevOps Alert - {severity}] {subject}"

    try:
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=full_subject[:100],
            Message=full_message
        )
        return {
            'success': True,
            'message_id': response['MessageId'],
            'subject': full_subject,
            'severity': severity
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── Lambda Handler ────────────────────────────────────────────

def lambda_handler(event, context):
    """Route to correct tool.
    Gateway sends: event = inputSchema properties (e.g. {"function_name": "..."}),
    tool name in context.client_context.custom["bedrockAgentCoreToolName"]
    Direct invocation sends: event = {"action": "tool_name", ...args}
    """

    # Gateway invocation: get tool name from context
    action = event.get('action')  # direct invocation
    if not action and context.client_context and context.client_context.custom:
        tool_full = context.client_context.custom.get('bedrockAgentCoreToolName', '')
        delimiter = '___'
        if delimiter in tool_full:
            action = tool_full[tool_full.index(delimiter) + len(delimiter):]
        # print(f'INVOKE_PATH: MCP_GATEWAY action={action}')  # uncomment to verify MCP path
    # elif action:
    #     print(f'INVOKE_PATH: DIRECT action={action}')
    # else:
    #     print(f'INVOKE_PATH: UNKNOWN event={str(event)[:100]}')
    
    try:
        if action == 'get_cloudwatch_logs':
            result = get_cloudwatch_logs(
                log_group_name=event['log_group_name'],
                hours=event.get('hours', 1),
                filter_pattern=event.get('filter_pattern', '')
            )
        elif action == 'get_lambda_errors':
            result = get_lambda_errors(
                function_name=event['function_name'],
                hours=event.get('hours', 1)
            )
        elif action == 'get_metric_stats':
            result = get_metric_stats(
                namespace=event['namespace'],
                metric_name=event['metric_name'],
                dimension_name=event['dimension_name'],
                dimension_value=event['dimension_value'],
                hours=event.get('hours', 1)
            )
        elif action == 'list_lambda_functions':
            result = list_lambda_functions()
        elif action == 'get_cost_summary':
            result = get_cost_summary(days=event.get('days', 30))
        elif action == 'get_service_breakdown':
            result = get_service_breakdown(days=event.get('days', 30))
        elif action == 'send_alert':
            result = send_alert(
                subject=event['subject'],
                message=event['message'],
                severity=event.get('severity', 'INFO')
            )
        else:
            result = {'error': f'Unknown action: {action}'}

        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
