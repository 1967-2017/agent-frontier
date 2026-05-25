# payment-api Runbook

## Symptoms
- Elevated payment authorization latency
- Checkout failures or retries
- Increased downstream processor errors

## Checks
- Query p99 latency and error rate over the affected window
- Tail recent WARN and ERROR logs
- Review active incidents before mitigation

## Mitigation
- Run `restart_service` with `dry_run=true` first
- Escalate with `notify_oncall` for sustained high severity impact
- Execute restart only after explicit operator confirmation
