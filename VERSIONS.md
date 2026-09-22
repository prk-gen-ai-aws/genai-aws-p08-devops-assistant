# Version History

## ph1 (Current)
- DevOps Intelligence Assistant via natural language
- AgentCore Gateway (MCP endpoint) exposing Lambda as MCP tools
- Strands Agent connects to Gateway via streamable HTTP MCP client
- 5 tools: list_lambda_functions, get_lambda_errors, get_cost_summary, get_service_breakdown, send_alert
- AgentCore Runtime (CDK deployed, global scope agent)
- CloudWatch Logs, Cost Explorer, SNS email alerts
- Streamlit UI with 4 pages
- Test suite: 19 Lambda tool tests + 10 agent conversation tests (29 total)

## Key Design Decisions
- Single Lambda function for all 5 tools: single IAM role, single deployment, easier maintenance
- authorizerType=NONE for Gateway: simplest setup for portfolio (switch to AWS_IAM for production)
- Agent in global scope: conversation history persists across invocations within same AgentCore session
- Tool name from context not event: Gateway sends tool name in context.client_context.custom['bedrockAgentCoreToolName'], not in event payload
- credentialProviderConfigurations GATEWAY_IAM_ROLE: required for Lambda target creation
- streamable_http_client (not streamablehttp_client): correct import for MCP HTTP client

## Key Learnings
- AgentCore Gateway Lambda target event format: event = inputSchema properties directly, tool name in context.client_context.custom['bedrockAgentCoreToolName'] — NOT in event payload
- Gateway requires credentialProviderConfigurations on target creation: {"credentialProviderType": "GATEWAY_IAM_ROLE"}
- MCP client import: from mcp.client.streamable_http import streamable_http_client (not streamablehttp_client)
- MCP client inside entrypoint (not module load): module-level init causes 30s AgentCore timeout
- CloudWatch Live Tail for real-time verification: aws logs start-live-tail > aws logs tail --follow
- AWS_REGION is reserved Lambda env var: cannot be set manually in --environment Variables
- Gateway tool schema: "default" field not supported in inlinePayload properties
- Agent global scope = conversation history: same pattern as P07, critical for multi-turn

## MCP Path Verification
To verify Streamlit → AgentCore Runtime → MCP → Gateway → Lambda path:
1. Uncomment print statement in lambda_tools.py (search for INVOKE_PATH)
2. Deploy Lambda update
3. Run: aws logs start-live-tail --log-group-identifiers "arn:aws:logs:us-east-1:ACCOUNT:log-group:/aws/lambda/p08-ph1-devops-assistant-dev-tools" --log-event-filter-pattern "INVOKE_PATH" --mode print-only
4. Invoke app in second terminal
5. See: INVOKE_PATH: MCP_GATEWAY action=list_lambda_functions

## ph2 Roadmap
- AgentCore Observability (CloudWatch GenAI dashboard)
- Multi-agent: Monitor Agent + Cost Agent + Alert Agent (supervisor pattern)
- Gateway authorizerType=AWS_IAM (production security)
- Real-time CloudWatch metrics dashboard in Streamlit
- Slack integration (replace SNS email alerts)
