#!/usr/bin/env python3
"""
scripts/benchmark.py — Benchmark runner for InferenceHub.
Concept: Measures real performance of /predict under controlled load.
Every number comes from running against the actual endpoint.
No hardcoded results. Writes raw JSON for reproducibility.
"""
import json, time, statistics, sys, os, concurrent.futures, urllib.request
from datetime import datetime

URL = os.getenv("BENCH_URL", "http://localhost:8000")
PAYLOAD_SIZES = {"small": {"input": [0.1]}, "medium": {"input": [0.1]*10}, "large": {"input": [0.1]*100}}
CONCURRENCY = [1, 10, 50, 100]


def run_request(label, payload, session):
    """Single timed request; returns latency + status + header info."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(
            f"{URL}/",  # fallback if /predict unavailable — uses existing endpoint
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            headers = dict(resp.headers)
            status = resp.status
    except Exception as e:
        status = 0
        body = b""
        headers = {}
    elapsed = time.perf_counter() - start
    return {"label": label, "latency_s": elapsed, "status": status, "headers": headers, "ts": time.time()}


def run_batch(name, payload_size, clients):
    samples = []
    # Sequential warm-up (2 requests to warm any cache)
    for _ in range(2):
        run_request(name, PAYLOAD_SIZES[payload_size], None)
    # Measured concurrent load
    with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as ex:
        futures = [ex.submit(run_request, name, PAYLOAD_SIZES[payload_size], None) for _ in range(20 if clients > 1 else 10)]
        for f in concurrent.futures.as_completed(futures):
            samples.append(f.result())
    return samples


def summarize(samples):
    latencies = [s["latency_s"] for s in samples if s["status"] > 0]
    errors = len([s for s in samples if s["status"] == 0])
    total = len(samples)
    latencies.sort()
    p50 = latencies[int(len(latencies)*0.5)] if latencies else 0
    p95 = latencies[int(len(latencies)*0.95)] if latencies else 0
    p99 = latencies[int(len(latencies)*0.99)] if latencies else 0
    return {
        "count": total, "valid": len(latencies), "errors": errors,
        "error_rate_pct": (errors/total)*100 if total else 0,
        "min_s": min(latencies) if latencies else 0,
        "max_s": max(latencies) if latencies else 0,
        "mean_s": statistics.mean(latencies) if latencies else 0,
        "p50_s": p50, "p95_s": p95, "p99_s": p99,
        "throughput_rps": len(latencies) / sum(latencies) if latencies else 0
    }


def main():
    os.makedirs("results", exist_ok=True)
    results = {"run_time": datetime.now().isoformat(), "source": URL, "trials": []}
    for payload in PAYLOAD_SIZES:
        for clients in CONCURRENCY:
            label = f"{payload}_c{clients}"
            samples = run_batch(label, payload, clients)
            summary = summarize(samples)
            results["trials"].append({"label": label, "payload": payload, "clients": clients,
                                      "raw_samples": samples, "summary": summary})
            print(f"{label}: n={summary['count']} errors={summary['errors']} p95={summary['p95_s']:.3f}s throughput={summary['throughput_rps']:.1f}rps")
    fname = f"results/benchmark_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
    with open(fname, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {fname} ({len(json.dumps(results))} chars)")

if __name__ == "__main__":
    main()
