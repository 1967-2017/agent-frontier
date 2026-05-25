# user-api Runbook

## Symptoms
- Login failures
- Token refresh delays
- Profile read latency

## Checks
- Query p99 latency and error rate
- Tail WARN and ERROR logs
- Inspect active incidents for authentication impact

## Mitigation
- Prefer dry-run restart before service changes
- Notify on-call for authentication-impacting incidents
