"""
P08 DevOps Assistant — Agent Conversation Test Suite
Run: python3 ph1/tests/test_agent_conversation.py
"""
import boto3
import json
import uuid
import time
import sys

RUNTIME_ARN = 'arn:aws:bedrock-agentcore:us-east-1:759802535955:runtime/p08DevOpsAssistant_p08DevOpsAssistant-LWscS67usw'
REGION      = 'us-east-1'

client = boto3.client('bedrock-agentcore', region_name=REGION)

passed = 0
failed = 0
errors = []

def invoke(prompt, session_id=None):
    kwargs = {
        "agentRuntimeArn": RUNTIME_ARN,
        "payload": json.dumps({"prompt": prompt}).encode(),
        "qualifier": "DEFAULT"
    }
    if session_id:
        kwargs["runtimeSessionId"] = session_id

    response = client.invoke_agent_runtime(**kwargs)
    session_id = response.get('runtimeSessionId')
    raw = response['response'].read().decode('utf-8')
    try:
        text = json.loads(raw)
    except:
        text = raw.strip()
    return str(text), session_id

def new_session():
    return str(uuid.uuid4())

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✅ {name}")
        passed += 1
    except AssertionError as e:
        print(f"  ❌ {name}")
        print(f"     {e}")
        failed += 1
        errors.append(name)
    except Exception as e:
        print(f"  ❌ {name} — ERROR: {e}")
        failed += 1
        errors.append(name)


# ════════════════════════════════════════════════════════════════
# GROUP 1: Basic queries
# ════════════════════════════════════════════════════════════════
print("\n🔧 Group 1: Basic queries")

def test_list_functions():
    r, _ = invoke("List all my Lambda functions")
    assert any(w in r.lower() for w in ["lambda", "function", "python"]), \
        f"Expected Lambda functions list, got: {r[:200]}"

test("list Lambda functions", test_list_functions)

def test_cost_query():
    r, _ = invoke("How much am I spending on AWS this month?")
    assert any(w in r.lower() for w in ["cost", "spend", "usd", "$", "free"]), \
        f"Expected cost info, got: {r[:200]}"

test("monthly cost query", test_cost_query)

def test_service_breakdown():
    r, _ = invoke("Which AWS services am I using and what do they cost?")
    assert any(w in r.lower() for w in ["service", "cost", "s3", "bedrock", "lambda"]), \
        f"Expected service breakdown, got: {r[:200]}"

test("service cost breakdown", test_service_breakdown)

def test_out_of_scope():
    r, _ = invoke("What is the weather in New York?")
    assert any(w in r.lower() for w in ["devops", "aws", "redirect", "help", "lambda", "infrastructure"]), \
        f"Expected out-of-scope redirect, got: {r[:200]}"

test("out of scope query redirected", test_out_of_scope)


# ════════════════════════════════════════════════════════════════
# GROUP 2: Lambda monitoring
# ════════════════════════════════════════════════════════════════
print("\n🔍 Group 2: Lambda monitoring")

def test_check_errors():
    r, _ = invoke("Check p07 shopping agent Lambda for errors in the last 24 hours")
    assert any(w in r.lower() for w in ["error", "healthy", "log", "p07", "shopping"]), \
        f"Expected error check result, got: {r[:200]}"

test("check Lambda errors", test_check_errors)

def test_function_status():
    r, _ = invoke("Is p08-ph1-devops-assistant-dev-tools running without errors?")
    assert any(w in r.lower() for w in ["error", "healthy", "running", "log", "p08"]), \
        f"Expected function status, got: {r[:200]}"

test("check specific function status", test_function_status)


# ════════════════════════════════════════════════════════════════
# GROUP 3: Alert sending
# ════════════════════════════════════════════════════════════════
print("\n🔔 Group 3: Alert sending")

def test_send_info_alert():
    r, _ = invoke("Send an INFO alert saying the deployment was successful")
    assert any(w in r.lower() for w in ["alert", "sent", "success", "notification", "sns"]), \
        f"Expected alert confirmation, got: {r[:200]}"

test("send INFO alert", test_send_info_alert)

def test_send_warning_alert():
    r, _ = invoke("Send a WARNING alert: Lambda error rate increased")
    assert any(w in r.lower() for w in ["alert", "sent", "warning", "notification"]), \
        f"Expected warning alert, got: {r[:200]}"

test("send WARNING alert", test_send_warning_alert)


# ════════════════════════════════════════════════════════════════
# GROUP 4: Multi-turn context
# ════════════════════════════════════════════════════════════════
print("\n💬 Group 4: Multi-turn context")

def test_multiturn_followup():
    session = new_session()
    r1, session = invoke("List all my Lambda functions", session)
    assert "lambda" in r1.lower() or "function" in r1.lower(), "Turn 1 should list functions"
    time.sleep(1)
    r2, _ = invoke("Which of those has the longest timeout?", session)
    assert any(w in r2.lower() for w in ["timeout", "300", "financial", "p03", "second"]), \
        f"Expected follow-up about timeout, got: {r2[:200]}"

test("follow-up question uses previous context", test_multiturn_followup)

def test_multiturn_alert_after_check():
    session = new_session()
    r1, session = invoke("Check p07 Lambda for errors", session)
    assert any(w in r1.lower() for w in ["error", "healthy", "log"]), "Turn 1 should check errors"
    time.sleep(1)
    r2, _ = invoke("Send an alert with the findings", session)
    assert any(w in r2.lower() for w in ["alert", "sent", "notification", "sns"]), \
        f"Expected alert sent, got: {r2[:200]}"

test("send alert based on previous check", test_multiturn_alert_after_check)


# ════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════
total = passed + failed
print(f"\n{'='*50}")
print(f"TEST RESULTS: {passed}/{total} passed")
if errors:
    print("FAILED TESTS:")
    for e in errors:
        print(f"  ❌ {e}")
else:
    print("✅ All tests passed!")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
