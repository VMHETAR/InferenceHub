# How to read the benchmark numbers

Audience: AI engineering — you need to know if this inference endpoint can serve production traffic.

## Metrics

- **Latency (p50/p95/p99)** — time from request sent to response received. p95 means 95% of requests finish within this time. For serving, p95 < 200ms is typical.
- **Throughput (req/sec)** — total valid requests divided by total wall-clock time of the trial. Higher = more load handled.
- **Error rate** — requests that return non-2xx / time out / crash, divided by total requests. < 0.1% is production-grade.
- **Cache hit rate** — second identical payload should be faster (Redis `get`). Measured by comparing first vs second latency; precise rate requires `MONITOR` or header inspection.

## Environment disclaimer

**Numbers depend on hardware, network, model size, container resources, and whether Redis/Postgres are co-located.** Always re-run `make benchmark` on your target environment (local Docker vs AWS ECS) before making architectural decisions.

This project defaults to local Docker (`docker-compose.yml`). AWS deployment (`terraform/`) uses Fargate + RDS + ElastiCache — numbers will differ.

## Reading a result file

`results/benchmark_YYYY-MM-DD_HH-MM.json` contains:
- `run_time` — when the benchmark started
- `source` — endpoint URL used
- `trials[]` — each payload/client combination with `summary` (stats) + `raw_samples` (every request)

Generate plots from the JSON file (not hardcoded):
```bash
python3 -c "
import json
with open('results/latest.json') as f: data=json.load(f)
# plot latency distribution from raw_samples
"
```n