"""
P08 DevOps Assistant — AgentCore Gateway Setup
Creates Gateway with NONE auth (portfolio/dev) + Lambda target
"""
import boto3
import json
import time

AWS_REGION   = 'us-east-1'
LAMBDA_ARN   = 'arn:aws:lambda:us-east-1:759802535955:function:p08-ph1-devops-assistant-dev-tools'
GATEWAY_NAME = 'p08DevOpsGateway'

# ── IAM Role for Gateway ─────────────────────────────────────
def create_gateway_role():
    iam = boto3.client('iam', region_name=AWS_REGION)
    role_name = 'p08-ph1-devops-assistant-dev-gateway-role'

    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }),
            Description="P08 DevOps Assistant Gateway Role"
        )
        role_arn = response['Role']['Arn']
        print(f"Created gateway role: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)['Role']['Arn']
        print(f"Using existing gateway role: {role_arn}")

    # Attach Lambda invoke policy
    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName='AllowLambdaInvoke',
            PolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": LAMBDA_ARN
                }]
            })
        )
        print("Lambda invoke permission added to gateway role")
    except Exception as e:
        print(f"Policy error (may already exist): {e}")

    # Allow Lambda to be invoked by gateway role
    lambda_client = boto3.client('lambda', region_name=AWS_REGION)
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_ARN,
            StatementId='AllowGatewayInvoke',
            Action='lambda:InvokeFunction',
            Principal='bedrock-agentcore.amazonaws.com'
        )
        print("Lambda resource policy updated")
    except lambda_client.exceptions.ResourceConflictException:
        print("Lambda resource policy already exists")

    time.sleep(5)  # Wait for IAM propagation
    return role_arn


# ── Create Gateway ────────────────────────────────────────────
def create_gateway(role_arn):
    client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)

    try:
        response = client.create_gateway(
            name=GATEWAY_NAME,
            roleArn=role_arn,
            protocolType='MCP',
            authorizerType='NONE',
            description='P08 DevOps Assistant Gateway — Lambda tools via MCP'
        )
        gateway_id  = response['gatewayId']
        gateway_url = response['gatewayUrl']
        print(f"Gateway created: {gateway_id}")
        print(f"Gateway URL: {gateway_url}")
        return gateway_id, gateway_url
    except Exception as e:
        print(f"Gateway creation error: {e}")
        raise


# ── Create Lambda Target ──────────────────────────────────────
def create_lambda_target(gateway_id):
    client = boto3.client('bedrock-agentcore-control', region_name=AWS_REGION)

    # Tool schema — defines all 7 tools in our Lambda
    tool_schema = [
        {
            "name": "list_lambda_functions",
            "description": "List all Lambda functions in the AWS account with their runtime, memory and last modified date",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_cloudwatch_logs",
            "description": "Get recent CloudWatch logs from a specific log group",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "log_group_name": {"type": "string", "description": "CloudWatch log group name e.g. /aws/lambda/my-function"},
                    "hours": {"type": "integer", "description": "Number of hours to look back (default 1)"},
                    "filter_pattern": {"type": "string", "description": "CloudWatch filter pattern e.g. ERROR"}
                },
                "required": ["log_group_name"]
            }
        },
        {
            "name": "get_lambda_errors",
            "description": "Get recent ERROR log entries from a Lambda function's CloudWatch logs",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "function_name": {"type": "string", "description": "Lambda function name e.g. p07-ph1-shopping-agent-dev-tools"},
                    "hours": {"type": "integer", "description": "Number of hours to look back (default 1)"}
                },
                "required": ["function_name"]
            }
        },
        {
            "name": "get_metric_stats",
            "description": "Get CloudWatch metric statistics for a specific AWS resource",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "CloudWatch namespace e.g. AWS/Lambda"},
                    "metric_name": {"type": "string", "description": "Metric name e.g. Errors, Duration, Invocations"},
                    "dimension_name": {"type": "string", "description": "Dimension name e.g. FunctionName"},
                    "dimension_value": {"type": "string", "description": "Dimension value e.g. my-function-name"},
                    "hours": {"type": "integer", "description": "Number of hours to look back (default 1)"}
                },
                "required": ["namespace", "metric_name", "dimension_name", "dimension_value"]
            }
        },
        {
            "name": "get_cost_summary",
            "description": "Get total AWS cost summary for the last N days",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days to look back (default 30)"}
                },
                "required": []
            }
        },
        {
            "name": "get_service_breakdown",
            "description": "Get AWS cost breakdown by service for the last N days, sorted by cost descending",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days to look back (default 30)"}
                },
                "required": []
            }
        },
        {
            "name": "send_alert",
            "description": "Send a DevOps alert notification via SNS",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Alert subject line"},
                    "message": {"type": "string", "description": "Alert message body"},
                    "severity": {"type": "string", "description": "Alert severity: INFO, WARNING, ERROR, CRITICAL"}
                },
                "required": ["subject", "message"]
            }
        }
    ]

    try:
        response = client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name='DevOpsLambdaTarget',
            targetConfiguration={
                'mcp': {
                    'lambda': {
                        'lambdaArn': LAMBDA_ARN,
                        'toolSchema': {
                            'inlinePayload': tool_schema
                        }
                    }
                }
            },
            description='DevOps Lambda tools exposed via MCP'
        )
        target_id = response['targetId']
        print(f"Lambda target created: {target_id}")
        return target_id
    except Exception as e:
        print(f"Target creation error: {e}")
        raise


# ── Main ──────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Setting up AgentCore Gateway for P08 DevOps Assistant...")
    print("="*60)

    # Step 1: Create IAM role
    print("\n[1/3] Creating Gateway IAM role...")
    role_arn = create_gateway_role()

    # Step 2: Create Gateway
    print("\n[2/3] Creating AgentCore Gateway...")
    gateway_id, gateway_url = create_gateway(role_arn)

    # Step 3: Create Lambda target
    print("\n[3/3] Creating Lambda target...")
    target_id = create_lambda_target(gateway_id)

    # Save config
    config = {
        'gateway_id': gateway_id,
        'gateway_url': gateway_url,
        'target_id': target_id,
        'lambda_arn': LAMBDA_ARN,
        'role_arn': role_arn
    }
    with open('gateway_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("\n" + "="*60)
    print("✅ Gateway setup complete!")
    print(f"Gateway ID:  {gateway_id}")
    print(f"Gateway URL: {gateway_url}")
    print(f"Target ID:   {target_id}")
    print("\nConfig saved to gateway_config.json")
    print("\nAdd to .env:")
    print(f"AGENTCORE_GATEWAY_URL={gateway_url}")
