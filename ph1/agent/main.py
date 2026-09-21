"""
P08 DevOps Intelligence Assistant — Strands Agent
Uses Lambda tools directly (same pattern as P07)
AgentCore Gateway + MCP demonstrated separately
"""
import os
import json
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

LAMBDA_NAME = os.environ.get("LAMBDA_TOOLS_NAME", "p08-ph1-devops-assistant-dev-tools")
MODEL_ID    = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

lambda_client = boto3.client("lambda")

def invoke_lambda(payload: dict) -> dict:
    response = lambda_client.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps(payload).encode()
    )
    result = json.loads(response["Payload"].read())
    return json.loads(result["body"])

@tool
def list_lambda_functions() -> str:
    """List all Lambda functions in the AWS account with runtime, memory and last modified date."""
    return json.dumps(invoke_lambda({"action": "list_lambda_functions"}))

@tool
def get_lambda_errors(function_name: str, hours: int = 1) -> str:
    """Get recent ERROR log entries from a Lambda function.
    
    Args:
        function_name: Lambda function name e.g. p07-ph1-shopping-agent-dev-tools
        hours: Number of hours to look back (default 1)
    """
    return json.dumps(invoke_lambda({
        "action": "get_lambda_errors",
        "function_name": function_name,
        "hours": hours
    }))

@tool
def get_cost_summary(days: int = 30) -> str:
    """Get total AWS cost summary for the last N days.
    
    Args:
        days: Number of days to look back (default 30)
    """
    return json.dumps(invoke_lambda({"action": "get_cost_summary", "days": days}))

@tool
def get_service_breakdown(days: int = 30) -> str:
    """Get AWS cost breakdown by service sorted by cost descending.
    
    Args:
        days: Number of days to look back (default 30)
    """
    return json.dumps(invoke_lambda({"action": "get_service_breakdown", "days": days}))

@tool
def send_alert(subject: str, message: str, severity: str = "INFO") -> str:
    """Send a DevOps alert notification via SNS.
    
    Args:
        subject: Alert subject line
        message: Alert message body
        severity: INFO, WARNING, ERROR, or CRITICAL
    """
    return json.dumps(invoke_lambda({
        "action": "send_alert",
        "subject": subject,
        "message": message,
        "severity": severity
    }))

SYSTEM_PROMPT = """You are a DevOps Intelligence Assistant for AWS infrastructure.
You help engineers monitor, troubleshoot, and optimize their AWS resources.

## Tools available:
- list_lambda_functions: List all Lambda functions in the account
- get_lambda_errors: Get recent ERROR logs from a Lambda function
- get_cost_summary: Get total AWS cost for the last N days
- get_service_breakdown: Get cost breakdown by AWS service
- send_alert: Send a DevOps alert notification via SNS

## Rules:
1. For monitoring questions use get_lambda_errors or list_lambda_functions
2. For cost questions use get_cost_summary or get_service_breakdown
3. For alerts use send_alert with appropriate severity
4. Always summarize findings clearly with actionable insights
5. For Lambda errors: show timestamp, message, and suggest likely cause
6. For costs: show total and top services by spend
7. Out of scope: politely redirect to DevOps topics
"""

app = BedrockAgentCoreApp()

_model = BedrockModel(model_id=MODEL_ID)
_agent = Agent(
    model=_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[list_lambda_functions, get_lambda_errors, get_cost_summary,
           get_service_breakdown, send_alert],
    callback_handler=None
)

@app.entrypoint
async def agent_entrypoint(payload: dict) -> str:
    prompt = payload.get("prompt", "")
    response = await _agent.invoke_async(prompt)
    return str(response)

if __name__ == "__main__":
    app.run()
