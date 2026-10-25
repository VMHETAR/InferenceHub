# Methodology — Evaluation & Benchmarking

## Why we benchmark

Inference serving has hard constraints: users wait milliseconds; errors compound at scale; resource costs scale with load. We measure before deploying, not after.

## Load test methodology

1. **Warm-up** — 2 sequential requests before measurement (caches, connections, ONNX load)
2. **Sample size** — 10 sequential or 20 concurrent per trial (enough for percentile stability, not so many that runs take hours)
3. **Concurrent clients** — 1, 10, 50, 100 (shows when throughput flattens or errors rise)
4. **Payload sizes** — small (1 float), medium (10), large (100) (shows batch overhead)
5. **Statistical confidence** — percentiles (p50/p95/p99) rather than mean alone; mean is misleading with long-tail latency

## Metrics that matter for inference serving

- **Latency** — user-facing. p95 is the SLA metric (most users see this).
- **Throughput** — capacity planning. If peak is 80% of max, you need scaling.
- **Error rate** — reliability. High error at high load indicates resource exhaustion (memory, DB connections, thread pool).
- **Cache hit rate** — cost / latency optimization. Redis saves DB queries; low hit rate means cache is misconfigured or invalidated too aggressively.
- **Resource utilization** — CPU/memory per task; tracked via CloudWatch (not this benchmark, but needed for full evaluation)

## Comparing baselines (why it matters)

Without baselines you don't know *why* something is fast. We compare against:
- Direct Postgres (no Redis cache) — proves cache helps
- No batch optimization — proves concurrent load handling helps

Real delta (e.g., "Redis cache: 4.2x faster p95") proves architectural choices have impact. Without this comparison, you might attribute speed to faster hardware, not design.
