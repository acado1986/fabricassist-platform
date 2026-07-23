#!/usr/bin/env python3
"""Bounded dependency-free metadata load smoke with explicit p95 gates."""

from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time
import urllib.error
import urllib.request


def request(url: str) -> tuple[float, bool]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            ok = response.status == 200
    except (urllib.error.URLError, TimeoutError):
        ok = False
    return time.perf_counter() - started, ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--p95-ms", type=float, default=500)
    args = parser.parse_args()
    if not 1 <= args.duration <= 300 or not 1 <= args.concurrency <= 100:
        parser.error("duration must be 1..300 and concurrency must be 1..100")
    endpoint = args.url.rstrip("/") + "/api/v1/health/ready"
    deadline = time.monotonic() + args.duration
    samples: list[float] = []
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        while time.monotonic() < deadline:
            for duration, ok in pool.map(request, [endpoint] * args.concurrency):
                samples.append(duration * 1000)
                failures += int(not ok)
    p95 = statistics.quantiles(samples, n=100, method="inclusive")[94]
    error_rate = failures / len(samples)
    print(
        f"requests={len(samples)} failures={failures} "
        f"error_rate={error_rate:.4f} p95_ms={p95:.1f}"
    )
    return 0 if error_rate <= 0.01 and p95 <= args.p95_ms else 1


if __name__ == "__main__":
    raise SystemExit(main())
