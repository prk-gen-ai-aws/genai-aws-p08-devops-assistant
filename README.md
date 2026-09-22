# DevOps Intelligence Assistant
Natural language interface to AWS infrastructure monitoring, cost analysis, and alerting — powered by Amazon Bedrock AgentCore Runtime, AgentCore Gateway (MCP), Strands Agents, Lambda, and CloudWatch.

Ask anything about your AWS infrastructure: list Lambda functions, check for errors, analyze costs, send alerts. The agent remembers context within a session — ask a follow-up and it knows what you mean.

[View on GitHub](https://github.com/prk-gen-ai-aws/genai-aws-p08-devops-assistant)

---

## How It Works

1. You ask a DevOps question: "Check p07 Lambda for errors in the last 24 hours"
2. The Strands Agent reasons about your query and selects the right tool
3. The agent calls the tool via MCP protocol through AgentCore Gateway
4. AgentCore Gateway invokes the Lambda function with the tool name in context
5. Lambda queries AWS APIs (CloudWatch, Cost Explorer, SNS) and returns results
6. The agent summarizes findings and offers actionable next steps

---

## New Capabilities vs P07

```
P07: Strands Agent → Lambda (direct invocation) → DynamoDB
P08: Strands Agent → MCP → AgentCore Gateway → Lambda → AWS APIs
```

P08 introduces AgentCore Gateway — a managed MCP (Model Context Protocol) endpoint that exposes Lambda tools as MCP tools. The agent discovers and calls tools via the MCP protocol rather than direct boto3 invocation. This is the key architectural advancement over P07.

---

## Supported Interactions

- List Lambda functions: "List all my Lambda functions"
- Check errors: "Check p07 shopping agent Lambda for errors in the last 24 hours"
- Cost summary: "How much am I spending on AWS this month?"
- Service breakdown: "Which AWS services am I using and what do they cost?"
- Send alert: "Send a WARNING alert: Lambda error rate increased"
- Multi-turn: "Which of those has the longest timeout?" (remembers previous results)
- Out of scope: Handled gracefully ("What is the weather?" → redirected to DevOps topics)

---

## Architecture

Architecture diagram: ph1/docs/architecture-ph1.png

```
Streamlit (local)
  └── boto3 invoke_agent_runtime + session_id
        └── AgentCore Runtime (CDK deployed)
              └── Strands Agent (Claude Haiku 4.5) [global scope]
                    └── MCP protocol
                          └── AgentCore Gateway (MCP endpoint)
                                └── Lambda (single function · 5 tools)
                                      ├── list_lambda_functions → AWS Lambda API
                                      ├── get_lambda_errors     → CloudWatch Logs
                                      ├── get_cost_summary      → Cost Explorer
                                      ├── get_service_breakdown → Cost Explorer
                                      └── send_alert            → SNS
```

**Key design decision — AgentCore Gateway:**
Lambda tools are registered in the Gateway as an MCP target (inlinePayload schema).
The agent connects to the Gateway URL via streamable HTTP and discovers tools automatically.
The Gateway invokes Lambda with the tool name in context.client_context.custom['bedrockAgentCoreToolName'].
Lambda reads the tool name from context (not from the event payload) and routes accordingly.

**Key design decision — Agent in global scope:**
Same pattern as P07 — Strands Agent initialized outside the entrypoint function.
Global scope ensures conversation history persists across invocations within the same AgentCore session.

**Short-term memory:**
AgentCore Runtime assigns session_id on first call (response['runtimeSessionId']).
Using the same session_id routes to the same container — history preserved within a session.

---

## How to Verify the MCP Path

To confirm that tool calls go through Gateway → Lambda (not direct invocation):

Step 1 — Add print statement to Lambda (already commented in lambda_tools.py):
    # Uncomment in lambda_handler:
    # print(f'INVOKE_PATH: MCP_GATEWAY action={action}')

Step 2 — Start CloudWatch Live Tail in Terminal 1:
    aws logs start-live-tail \
      --log-group-identifiers "arn:aws:logs:us-east-1:YOUR_ACCOUNT_ID:log-group:/aws/lambda/p08-ph1-devops-assistant-dev-tools" \
      --log-event-filter-pattern "INVOKE_PATH" \
      --mode print-only \
      --region us-east-1

Step 3 — Invoke agent in Terminal 2:
    agentcore invoke --prompt "List all my Lambda functions" --stream

Step 4 — Terminal 1 shows within 1-2 seconds:
    INVOKE_PATH: MCP_GATEWAY action=list_lambda_functions

Note: Use aws logs start-live-tail (not aws logs tail --follow) for real-time streaming.
aws logs tail --follow polls every few seconds and can miss fast invocations.

---

## Project Structure

    genai-aws-p08-devops-assistant/
    ph1/
      agent/
        main.py          <- Strands agent + MCP client (global scope)
        lambda_tools.py  <- Lambda handler (5 tools + commented debug logging)
        pyproject.toml   <- uv project file (required by AgentCore CLI)
      app/
        main.py          <- Streamlit UI (chat interface)
        requirements.txt
      docs/
        architecture-ph1.png
      tests/
        test_lambda_tools.py       <- 19 tests (Lambda tools)
        test_agent_conversation.py <- 10 tests (AgentCore multi-turn)
    agentcore/
      agentcore.json     <- AgentCore CLI config
      aws-targets.json   <- Deployment target
      cdk/               <- CDK stack (TypeScript)
    cfn/
      template.yaml      <- Lambda IAM role + SNS topic
    gateway_config.json  <- AgentCore Gateway IDs and URL
    setup_gateway_p08.py <- Gateway setup script (run once)
    README.md
    VERSIONS.md
    .env.example
    .gitignore

---

## Tech Stack

- Frontend: Streamlit (Python) — runs locally
- Agent Framework: Strands Agents v1.0
- Agent Runtime: Amazon Bedrock AgentCore Runtime (managed, CDK deployed)
- Gateway: Amazon Bedrock AgentCore Gateway (MCP endpoint)
- Protocol: MCP (Model Context Protocol) via streamable HTTP
- Tools: AWS Lambda (Python 3.12, single function)
- Monitoring: Amazon CloudWatch Logs
- Cost: AWS Cost Explorer
- Alerts: Amazon SNS (email)
- AI Model: Amazon Bedrock — Claude Haiku 4.5
- IaC: CloudFormation (Lambda IAM + SNS) + CDK via AgentCore CLI (Runtime)
- Language: Python 3.12

---

## Prerequisites

- AWS account with CLI configured (aws configure)
- Python 3.12+
- Node.js 18+ (required for AgentCore CLI and CDK)
- Bedrock model access: Go to AWS Console → Amazon Bedrock → Model access → Enable "Claude Haiku 4.5 20251001"

Note: Throughout this guide, replace YOUR_ACCOUNT_ID with your 12-digit AWS account ID.
Find it by running: aws sts get-caller-identity --query Account --output text

One-time installations:
    sudo npm install -g @aws/agentcore
    sudo npm install -g aws-cdk
    pip install strands-agents bedrock-agentcore boto3 mcp
    curl -LsSf https://astral.sh/uv/install.sh | sh

One-time CDK bootstrap:
    cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1

---

## Fork and Deploy — Complete Guide

### Step 0 — Clone the repository

    git clone https://github.com/prk-gen-ai-aws/genai-aws-p08-devops-assistant.git
    cd genai-aws-p08-devops-assistant

### Step 1 — Create Python virtual environment

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r ph1/app/requirements.txt
    pip install strands-agents bedrock-agentcore boto3 mcp

Copy .env.example to .env:

    cp .env.example .env

The .env file contains only configuration values (no credentials or secrets).
It is gitignored and never committed to the repository.

Expected .env content after all steps:
    AWS_REGION=us-east-1
    AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT_ID:runtime/...
    AGENTCORE_GATEWAY_URL=https://YOUR_GATEWAY_ID.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
    AGENTCORE_GATEWAY_ID=YOUR_GATEWAY_ID
    AGENTCORE_GATEWAY_TARGET_ID=YOUR_TARGET_ID
    SNS_ALERT_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:p08-ph1-devops-assistant-dev-alerts

### Step 2 — Deploy CloudFormation stack (Lambda IAM role + SNS topic)

    aws cloudformation create-stack \
      --stack-name p08-ph1-devops-assistant-dev \
      --template-body file://cfn/template.yaml \
      --capabilities CAPABILITY_NAMED_IAM \
      --region us-east-1

    aws cloudformation wait stack-create-complete \
      --stack-name p08-ph1-devops-assistant-dev \
      --region us-east-1

Verify outputs:

    aws cloudformation describe-stacks \
      --stack-name p08-ph1-devops-assistant-dev \
      --query "Stacks[0].Outputs" --output table --region us-east-1

Expected: LambdaExecutionRoleArn and AlertTopicArn

### Step 3 — Deploy Lambda function

    cd ph1/agent
    zip lambda_tools.zip lambda_tools.py
    cd ../..

    aws lambda create-function \
      --function-name p08-ph1-devops-assistant-dev-tools \
      --runtime python3.12 \
      --role arn:aws:iam::YOUR_ACCOUNT_ID:role/p08-ph1-devops-assistant-dev-lambda-role \
      --handler lambda_tools.lambda_handler \
      --zip-file fileb://ph1/agent/lambda_tools.zip \
      --timeout 30 \
      --environment Variables="{SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:p08-ph1-devops-assistant-dev-alerts}" \
      --region us-east-1

If function already exists:

    aws lambda update-function-code \
      --function-name p08-ph1-devops-assistant-dev-tools \
      --zip-file fileb://ph1/agent/lambda_tools.zip \
      --region us-east-1

### Step 4 — Run the Lambda test suite

    python3 ph1/tests/test_lambda_tools.py

Expected: 19/19 tests passed

### Step 5 — Create AgentCore Gateway

Update setup_gateway_p08.py — edit LAMBDA_ARN at the top of the file (replace YOUR_ACCOUNT_ID):

    python3 setup_gateway_p08.py

Expected output:
    Gateway ID:  p08devopsgateway-xxxxxxxxxx
    Gateway URL: https://p08devopsgateway-xxxxxxxxxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
    Target ID:   XXXXXXXXXX
    Config saved to gateway_config.json

Update .env with the Gateway URL:
    AGENTCORE_GATEWAY_URL=https://p08devopsgateway-xxxxxxxxxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp

Verify Gateway is READY:

    python3 -c "
    import boto3, json
    client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
    gw = client.get_gateway(gatewayIdentifier='YOUR_GATEWAY_ID')
    print(f'Gateway status: {gw["status"]}')
    "
    # Expected: Gateway status: READY

### Step 6 — Update agentcore.json

Edit agentcore/agentcore.json — update environmentVariables with your Gateway URL:

    {
      "name": "p08DevOpsAssistant",
      "runtimes": [{
        "name": "p08DevOpsAssistant",
        "build": "CodeZip",
        "entrypoint": "main.py",
        "codeLocation": "ph1/agent/",
        "runtimeVersion": "PYTHON_3_12",
        "networkMode": "PUBLIC",
        "protocol": "HTTP",
        "environmentVariables": {
          "AGENTCORE_GATEWAY_URL": "https://YOUR_GATEWAY_ID.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
        }
      }]
    }

### Step 7 — Deploy AgentCore Runtime

    cd agentcore/cdk
    npm install        # if permission error: sudo npm install
    npx tsc            # compile TypeScript — required before deploy
    cd ../..
    agentcore deploy

### Step 8 — Add IAM permissions to AgentCore role

Step 8a — Get the AgentCore IAM role name:

    aws cloudformation describe-stack-resources \
      --stack-name AgentCore-p08DevOpsAssistant-default \
      --query "StackResources[?ResourceType=='AWS::IAM::Role'].PhysicalResourceId" \
      --output text --region us-east-1

Step 8b — Add DevOps tool permissions (replace AGENTCORE_ROLE_NAME):

    aws iam put-role-policy \
      --role-name AGENTCORE_ROLE_NAME \
      --policy-name AllowDevOpsTools \
      --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:FilterLogEvents","logs:DescribeLogGroups","cloudwatch:GetMetricStatistics","cloudwatch:ListMetrics","lambda:ListFunctions","ce:GetCostAndUsage","sns:Publish"],"Resource":"*"}]}'

Step 8c — Add Lambda invoke permission:

    aws iam put-role-policy \
      --role-name AGENTCORE_ROLE_NAME \
      --policy-name AllowLambdaInvoke \
      --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["lambda:InvokeFunction"],"Resource":"arn:aws:lambda:us-east-1:YOUR_ACCOUNT_ID:function:p08-ph1-devops-assistant-dev-tools"}]}'

### Step 9 — Subscribe email to SNS alerts

    aws sns subscribe \
      --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:p08-ph1-devops-assistant-dev-alerts \
      --protocol email \
      --notification-endpoint YOUR_EMAIL@example.com \
      --region us-east-1

Check your email inbox (and spam folder) for the confirmation email from no-reply@sns.amazonaws.com.
Click the confirmation link before testing alerts.

### Step 10 — Test the agent

    agentcore invoke --prompt "List all my Lambda functions" --stream

Expected: Table of Lambda functions with runtime, memory, timeout.

Test multi-turn (use session_id from previous response):

    agentcore invoke --session-id YOUR_SESSION_ID --prompt "Which one has the longest timeout?" --stream

Run conversation test suite:

    python3 ph1/tests/test_agent_conversation.py

Expected: 10/10 tests passed

### Step 11 — Run the Streamlit app

Get Runtime ARN and update .env:

    agentcore status
    echo "AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT_ID:runtime/..." >> .env

Run the app:

    streamlit run ph1/app/main.py

---

## Cost Estimate

- Lambda: free tier (1M requests/month) — negligible for portfolio
- CloudWatch Logs: free tier (first 5GB/month) — $0.00
- Cost Explorer: $0.01 per API request — negligible
- SNS: first 1000 email notifications free — $0.00
- Bedrock (Claude Haiku 4.5): approx USD 0.001 per conversation turn
- AgentCore Runtime: pay per invocation — negligible
- AgentCore Gateway: pay per invocation — negligible
- Total: less than USD 3.00 per month with daily testing

---

## Things to Consider at Scale

- Multi-user: session_id per user for conversation isolation
- Gateway auth: switch authorizerType from NONE to AWS_IAM for production
- CloudWatch: add log retention policy to avoid unbounded storage costs
- SNS: add filtering policies to route alerts by severity
- Lambda timeout: 30s is sufficient for CloudWatch + Cost Explorer queries
- Agent scope: global scope works for single-container; review for multi-instance deployments

---

## AWS Documentation References

- AgentCore Gateway: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html
- AgentCore Gateway Lambda target: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html
- MCP (Model Context Protocol): https://modelcontextprotocol.io/
- AgentCore Runtime: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html
- CloudWatch Logs Live Tail: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CloudWatchLogs_LiveTail.html
- Strands Agents MCP: https://strandsagents.com/latest/user-guide/concepts/tools/mcp/
- Cost Explorer API: https://docs.aws.amazon.com/cost-management/latest/userguide/ce-api.html

---

## Version History

See VERSIONS.md for details.

---

> Part of an ongoing series exploring Gen AI on AWS.
> Browse all projects: https://github.com/prk-gen-ai-aws
