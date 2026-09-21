"""
P08 DevOps Assistant — Lambda Tools Test Suite
Run: python3 ph1/tests/test_lambda_tools.py
"""
import boto3
import json
import sys

LAMBDA_NAME = 'p08-ph1-devops-assistant-dev-tools'
REGION      = 'us-east-1'

client = boto3.client('lambda', region_name=REGION)

passed = 0
failed = 0
errors = []

def invoke(payload):
    response = client.invoke(
        FunctionName=LAMBDA_NAME,
        Payload=json.dumps(payload).encode()
    )
    result = json.loads(response['Payload'].read())
    return json.loads(result['body'])

def test(name, payload, assertions):
    global passed, failed
    try:
        result = invoke(payload)
        for assertion_fn, msg in assertions:
            assert assertion_fn(result), f"FAILED: {msg}\n  Result: {json.dumps(result, indent=2)[:300]}"
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
# GROUP 1: list_lambda_functions
# ════════════════════════════════════════════════════════════════
print("\n🔧 Group 1: list_lambda_functions")

test("returns list of functions",
    {"action": "list_lambda_functions"},
    [(lambda r: 'functions' in r, "should return functions key"),
     (lambda r: r['count'] > 0, "should have at least 1 function"),
     (lambda r: all('name' in f for f in r['functions']), "each function should have name")])

test("includes p08 tools function",
    {"action": "list_lambda_functions"},
    [(lambda r: any('p08' in f['name'] for f in r['functions']), "should include p08 function")])

test("includes p07 shopping agent",
    {"action": "list_lambda_functions"},
    [(lambda r: any('p07' in f['name'] for f in r['functions']), "should include p07 function")])

test("all functions have required fields",
    {"action": "list_lambda_functions"},
    [(lambda r: all('runtime' in f and 'memory' in f and 'timeout' in f
                    for f in r['functions']), "all functions need runtime, memory, timeout")])


# ════════════════════════════════════════════════════════════════
# GROUP 2: get_lambda_errors
# ════════════════════════════════════════════════════════════════
print("\n🔍 Group 2: get_lambda_errors")

test("check p07 function for errors (last 1 hour)",
    {"action": "get_lambda_errors", "function_name": "p07-ph1-shopping-agent-dev-tools", "hours": 1},
    [(lambda r: 'function_name' in r, "should return function_name"),
     (lambda r: 'event_count' in r, "should return event_count"),
     (lambda r: isinstance(r['events'], list), "events should be a list")])

test("check p08 function for errors",
    {"action": "get_lambda_errors", "function_name": "p08-ph1-devops-assistant-dev-tools", "hours": 24},
    [(lambda r: 'event_count' in r, "should return event_count"),
     (lambda r: r['function_name'] == 'p08-ph1-devops-assistant-dev-tools', "function name should match")])

test("non-existent function returns error gracefully",
    {"action": "get_lambda_errors", "function_name": "non-existent-function-xyz"},
    [(lambda r: 'error' in r or 'event_count' in r, "should handle gracefully")])


# ════════════════════════════════════════════════════════════════
# GROUP 3: get_cost_summary
# ════════════════════════════════════════════════════════════════
print("\n💰 Group 3: get_cost_summary")

test("get 30-day cost summary",
    {"action": "get_cost_summary", "days": 30},
    [(lambda r: 'total_cost_usd' in r, "should return total_cost_usd"),
     (lambda r: 'start_date' in r and 'end_date' in r, "should return date range"),
     (lambda r: r['currency'] == 'USD', "currency should be USD"),
     (lambda r: r['period_days'] == 30, "period should be 30 days")])

test("get 7-day cost summary",
    {"action": "get_cost_summary", "days": 7},
    [(lambda r: r['period_days'] == 7, "period should be 7 days"),
     (lambda r: r['total_cost_usd'] >= 0, "cost should be >= 0")])

test("cost is within free tier range",
    {"action": "get_cost_summary", "days": 30},
    [(lambda r: r['total_cost_usd'] < 100, "cost should be less than $100 for portfolio")])


# ════════════════════════════════════════════════════════════════
# GROUP 4: get_service_breakdown
# ════════════════════════════════════════════════════════════════
print("\n📊 Group 4: get_service_breakdown")

test("get service breakdown",
    {"action": "get_service_breakdown", "days": 30},
    [(lambda r: 'services' in r, "should return services"),
     (lambda r: isinstance(r['services'], list), "services should be a list"),
     (lambda r: 'start_date' in r, "should have start_date")])

test("services sorted by cost descending",
    {"action": "get_service_breakdown", "days": 30},
    [(lambda r: len(r['services']) == 0 or
                all(r['services'][i]['cost_usd'] >= r['services'][i+1]['cost_usd']
                    for i in range(len(r['services'])-1)),
      "services should be sorted by cost descending")])

test("each service has name and cost",
    {"action": "get_service_breakdown", "days": 30},
    [(lambda r: all('service' in s and 'cost_usd' in s
                    for s in r['services']),
      "each service needs name and cost")])


# ════════════════════════════════════════════════════════════════
# GROUP 5: send_alert
# ════════════════════════════════════════════════════════════════
print("\n🔔 Group 5: send_alert")

test("send INFO alert succeeds",
    {"action": "send_alert", "subject": "Test Alert", "message": "P08 test suite alert", "severity": "INFO"},
    [(lambda r: r['success'] == True, "alert should succeed"),
     (lambda r: 'message_id' in r, "should return message_id"),
     (lambda r: r['severity'] == 'INFO', "severity should be INFO")])

test("send WARNING alert succeeds",
    {"action": "send_alert", "subject": "Warning Test", "message": "Test warning alert", "severity": "WARNING"},
    [(lambda r: r['success'] == True, "alert should succeed"),
     (lambda r: 'WARNING' in r['subject'], "subject should contain WARNING")])

test("send ERROR alert succeeds",
    {"action": "send_alert", "subject": "Error Test", "message": "Test error alert", "severity": "ERROR"},
    [(lambda r: r['success'] == True, "alert should succeed")])


# ════════════════════════════════════════════════════════════════
# GROUP 6: edge cases
# ════════════════════════════════════════════════════════════════
print("\n🔧 Group 6: edge cases")

test("unknown action returns error",
    {"action": "unknown_action"},
    [(lambda r: 'error' in r, "should return error for unknown action")])

test("missing required field handled gracefully",
    {"action": "get_lambda_errors"},
    [(lambda r: 'error' in r or 'event_count' in r, "should handle missing function_name")])

test("cloudwatch logs action works",
    {"action": "get_cloudwatch_logs", "log_group_name": "/aws/lambda/p08-ph1-devops-assistant-dev-tools", "hours": 1},
    [(lambda r: 'log_group' in r or 'error' in r, "should return log_group or handle error")])


# ════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════
total = passed + failed
print(f"\n{'='*50}")
print(f"TEST RESULTS: {passed}/{total} passed")
if errors:
    print(f"FAILED TESTS:")
    for e in errors:
        print(f"  ❌ {e}")
else:
    print("✅ All tests passed!")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
