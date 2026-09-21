"""
P08 DevOps Intelligence Assistant — Streamlit UI
"""
import streamlit as st
import boto3
import json
import uuid
import os
import re
from dotenv import load_dotenv

load_dotenv()

RUNTIME_ARN = os.getenv('AGENTCORE_RUNTIME_ARN', '')
AWS_REGION  = os.getenv('AWS_REGION', 'us-east-1')

st.set_page_config(
    page_title="DevOps Intelligence Assistant",
    page_icon="🛠️",
    layout="wide"
)

# ── Sidebar ──────────────────────────────────────────────────────
st.sidebar.title("🛠️ DevOps Assistant")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", ["Assistant", "How it works", "Architecture", "About"])
st.sidebar.markdown("---")
st.sidebar.caption("Built on AWS · Powered by AgentCore")
st.sidebar.caption("Strands Agents · Lambda · Gateway · MCP")


def invoke_agent(prompt, session_id=None):
    client = boto3.client('bedrock-agentcore', region_name=AWS_REGION)
    kwargs = {
        "agentRuntimeArn": RUNTIME_ARN,
        "payload": json.dumps({"prompt": prompt}).encode(),
        "qualifier": "DEFAULT"
    }
    if session_id:
        kwargs["runtimeSessionId"] = session_id

    response = client.invoke_agent_runtime(**kwargs)
    assigned_session = response.get('runtimeSessionId')
    raw = response['response'].read().decode('utf-8')
    try:
        text = json.loads(raw)
    except:
        text = raw.strip()
    return str(text), assigned_session


def new_session():
    return str(uuid.uuid4())


# ── Init session state ───────────────────────────────────────────
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []


# ════════════════════════════════════════════════════════════════
# PAGE 1: Assistant
# ════════════════════════════════════════════════════════════════
if page == "Assistant":
    st.title("🛠️ DevOps Intelligence Assistant")
    st.subheader("Monitor AWS resources, analyze costs, and send alerts in natural language")
    st.markdown("---")

    # Example prompts
    if not st.session_state.messages:
        st.markdown("### 💡 Try asking:")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔧 List all Lambda functions"):
                st.session_state.pending = "List all my Lambda functions"
            if st.button("💰 Monthly cost summary"):
                st.session_state.pending = "How much am I spending on AWS this month?"
        with col2:
            if st.button("🔍 Check for Lambda errors"):
                st.session_state.pending = "Check p07-ph1-shopping-agent-dev-tools for errors in the last 24 hours"
            if st.button("📊 Service cost breakdown"):
                st.session_state.pending = "Which AWS services am I using and what do they cost?"

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Handle button click
    if 'pending' in st.session_state:
        prompt = st.session_state.pop('pending')
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your AWS infrastructure..."):
                response, session_id = invoke_agent(prompt, st.session_state.session_id)
                if not st.session_state.session_id:
                    st.session_state.session_id = session_id
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask about your AWS infrastructure..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your AWS infrastructure..."):
                response, session_id = invoke_agent(prompt, st.session_state.session_id)
                if not st.session_state.session_id:
                    st.session_state.session_id = session_id
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

    # Session controls
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.session_state.session_id:
            st.caption(f"Session: {st.session_state.session_id[:16]}...")
        else:
            st.caption("Session: not started")
    with col2:
        if st.button("🔄 New Session"):
            st.session_state.messages = []
            st.session_state.session_id = None
            st.rerun()


# ════════════════════════════════════════════════════════════════
# PAGE 2: How it works
# ════════════════════════════════════════════════════════════════
elif page == "How it works":
    st.title("How it works")
    st.markdown("---")
    st.markdown("""
    **P08 DevOps Intelligence Assistant** is a natural language interface to your AWS infrastructure.

    **What you can do:**
    - List and inspect Lambda functions across your account
    - Check CloudWatch logs for Lambda errors
    - Get AWS cost summaries and service breakdowns
    - Send DevOps alerts via SNS

    **New capabilities vs P07:**
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**P07 Shopping Agent**")
        st.markdown("""
        - Single agent
        - Lambda tools (direct invocation)
        - DynamoDB data store
        - Multimodal image search
        """)
    with col2:
        st.markdown("**P08 DevOps Assistant**")
        st.markdown("""
        - Single agent + Gateway + MCP
        - Lambda tools via AgentCore Gateway
        - CloudWatch + Cost Explorer
        - SNS alerts
        """)

    st.markdown("---")
    st.markdown("### AgentCore Gateway + MCP")
    st.markdown("""
    Lambda tools are exposed as MCP (Model Context Protocol) endpoints via AgentCore Gateway.
    The agent connects to the Gateway URL and discovers tools automatically via the MCP protocol.
    This is the key new capability in P08 — tools are no longer hardcoded in the agent,
    they are dynamically discovered via a managed Gateway endpoint.
    """)

    st.markdown("### Short-term memory")
    st.markdown("""
    AgentCore Runtime maintains conversation context within a session via session_id
    (same pattern as P07). Ask a follow-up question and the agent remembers previous findings.
    """)


# ════════════════════════════════════════════════════════════════
# PAGE 3: Architecture
# ════════════════════════════════════════════════════════════════
elif page == "Architecture":
    st.title("Architecture")
    st.markdown("---")
    st.markdown("""
    ### P08 DevOps Intelligence Assistant

    ```
    Streamlit (local)
      └── boto3 invoke_agent_runtime + session_id
            └── AgentCore Runtime (CDK deployed)
                  └── Strands Agent (Claude Haiku 4.5)
                        └── Lambda Tools (direct invocation)
                              ├── list_lambda_functions  → AWS Lambda API
                              ├── get_lambda_errors      → CloudWatch Logs
                              ├── get_cost_summary       → Cost Explorer
                              ├── get_service_breakdown  → Cost Explorer
                              └── send_alert             → SNS

    AgentCore Gateway (MCP endpoint — separate capability):
      Gateway URL → MCP Protocol → Lambda Tools
      Demonstrated via: python3 setup_gateway_p08.py
    ```
    """)

    diagram_path = 'ph1/docs/architecture-ph1.png'
    if os.path.exists(diagram_path):
        st.image(diagram_path)
    else:
        st.info("Architecture diagram: ph1/docs/architecture-ph1.png")

    st.markdown("---")
    st.markdown("### Component breakdown")
    components = {
        "Streamlit (local)": "Chat UI. Sends prompts to AgentCore Runtime via boto3. Preserves session_id for multi-turn context.",
        "AgentCore Runtime (CDK)": "Managed container runtime. Hosts Strands agent. Maintains session context via session_id.",
        "Strands Agent (Claude Haiku 4.5)": "Autonomous agent. Routes queries to appropriate tools: monitoring, cost, or alerts.",
        "Lambda Tools (5 tools)": "list_lambda_functions, get_lambda_errors, get_cost_summary, get_service_breakdown, send_alert.",
        "CloudWatch Logs": "Source for Lambda error logs. Queried via filter_log_events API.",
        "Cost Explorer": "Source for AWS billing data. Queried via get_cost_and_usage API.",
        "SNS": "Alert notification service. Publishes alerts to p08-ph1-devops-assistant-dev-alerts topic.",
        "AgentCore Gateway": "Exposes Lambda tools as MCP endpoint. Enables tool discovery via MCP protocol.",
    }
    for name, desc in components.items():
        with st.expander(f"**{name}**"):
            st.markdown(desc)


# ════════════════════════════════════════════════════════════════
# PAGE 4: About
# ════════════════════════════════════════════════════════════════
elif page == "About":
    st.title("About this project")
    st.markdown("---")
    st.markdown("""
    ### Gen AI on AWS — Portfolio Project 8

    DevOps Intelligence Assistant — natural language interface to AWS infrastructure monitoring,
    cost analysis, and alerting.

    **New capabilities vs previous projects:**
    - AgentCore Gateway (MCP endpoint for Lambda tools)
    - MCP protocol (tool discovery via Gateway)
    - CloudWatch Logs integration
    - Cost Explorer integration
    - SNS alerting

    [View on GitHub](https://github.com/prk-gen-ai-aws/genai-aws-p08-devops-assistant)

    ---
    ### Series progression

    | Project | Capability |
    |---|---|
    | P05 | Single agent + Lambda tools |
    | P06 | Single agent + Memory |
    | P07 | Single agent + DynamoDB + Multimodal |
    | P08 | Single agent + Gateway + MCP ← this project |

    ---
    > Part of an ongoing series exploring Gen AI on AWS.
    > Browse all projects: https://github.com/prk-gen-ai-aws
    """)
