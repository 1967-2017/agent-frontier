# order-api Runbook

## Symptoms
- Queue depth growth
- Delayed order state transitions
- Event publishing lag

## Checks
- Query p99 latency and error rate
- Tail WARN and ERROR logs
- Check active incidents for correlated service impact

## Mitigation
- Dry-run restart before making changes
- Notify on-call if queue depth continues increasing
