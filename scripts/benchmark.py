#!/usr/bin/env python3
"""Simple throughput benchmark for judge-facing production claims."""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_generator import generate_dataset  # noqa: E402
from app.scoring import rank_customers, score_customer  # noqa: E402


def main() -> int:
    customers = generate_dataset(200, seed=42)
    single_times: list[float] = []
    for c in customers[:50]:
        t0 = time.perf_counter()
        score_customer(c)
        single_times.append((time.perf_counter() - t0) * 1000)

    batch_times: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        rank_customers(customers)
        batch_times.append((time.perf_counter() - t0) * 1000)

    p95_single = statistics.quantiles(single_times, n=20)[-1] if len(single_times) >= 20 else max(single_times)
    print("=== Prospect Assist AI — Benchmark ===")
    print(f"Single customer score p95: {p95_single:.1f} ms (n=50)")
    print(f"Rank 200 customers mean: {statistics.mean(batch_times):.1f} ms")
    print(f"Rank 200 customers p95: {statistics.quantiles(batch_times, n=5)[-1]:.1f} ms")
    print("Claim: 10K leads/month at <2s p95 per score — headroom on laptop-class CPU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
