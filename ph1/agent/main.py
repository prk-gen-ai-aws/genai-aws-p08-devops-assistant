"""
P08 DevOps Intelligence Assistant
AgentCore Runtime → MCP → AgentCore Gateway → Lambda
"""
import os
import asyncio
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamable_http_client as streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp

GATEWAY_URL = os.environ.get(
    "AGENTCORE_GATEWAY_URL",
    "https://p08devopsgateway-sivyq78u0i.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
)
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = """You are a DevOps Intelligence Assistant for AWS infrastructure.
You help engineers monitor, troubleshoot, and optimize their AWS resources.

## Tools available via MCP:
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
5. Out of scope: politely redirect to DevOps topics
"""

app = BedrockAgentCoreApp()

@app.entrypoint
async def agent_entrypoint(payload: dict) -> str:
    prompt = payload.get("prompt", "")

    mcp_client = MCPClient(
        lambda: streamablehttp_client(url=GATEWAY_URL)
    )

    model = BedrockModel(model_id=MODEL_ID)

    with mcp_client:
        tools = mcp_client.list_tools_sync()
        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            callback_handler=None
        )
        response = agent(prompt)
        return str(response)

if __name__ == "__main__":
    app.run()
