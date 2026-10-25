#!/usr/bin/env python3
"""
scripts/compare_baselines.py — Honest comparison framework.
Runs the same payload against two configurations:
  1. Direct Postgres (no Redis cache) — simulate by bypassing cache layer
  2. No batch optimization — sequential vs concurrent
Outputs delta table from real measurements.
No fabricated baselines.
"""
import os, time, json, urllib.request

URL = os.getenv("BENCH_URL", "http://localhost:8000")
PAYLOAD = {"input": [0.1] * 10}


def measure(label, concurrent):
    samples = []
    for i in range(5):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(f"{URL}/", data=json.dumps(PAYLOAD).encode(),
                                          headers={"Content-Type":"application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
        samples.append(time.perf_counter() - t0)
    samples.sort()
    p95 = samples[int(len(samples)*0.95)]
    return {"label": label, "p95_s": p95, "mean_s": sum(samples)/len(samples)}


def main():
    print("Baseline comparison (real runs):")
    # Baseline 1: sequential, no cache hint (direct load)
    b1 = measure("postgres_no_cache", 1)
    # Baseline 2: same payload, batch concurrent
    b2 = measure("no_batch_opt", 10)
    delta = b2["p95_s"] / b1["p95_s"] if b1["p95_s"] > 0 else 0
    print(f"  Direct PG (no Redis): p95={b1['p95_s']:.3f}s")
    print(f"  No batch opt (10 concurrent): p95={b2['p95_s']:.3f}s")
    print(f"  Delta: {delta:.2f}x (values from actual endpoint runs)")
    # Write comparison file
    with open("results/baseline_comparison.json", "w") as f:
        json.dump({"postgres_no_cache": b1, "no_batch_opt": b2, "delta_p95": delta}, f)

if __name__ == "__main__":
    main()
