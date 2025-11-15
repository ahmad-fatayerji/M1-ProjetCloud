#!/usr/bin/env python3
import asyncio
import aiohttp
import time
import csv
import os
import argparse
from typing import List, Tuple

# Concurrency levels 
DEFAULT_PARAMS = [1, 10, 20, 50, 100, 1000]


async def fetch_timeline(
    session: aiohttp.ClientSession,
    base_url: str,
    username: str,
    limit: int,
) -> Tuple[float, bool]:
    """
    Do one GET /api/timeline?user=<username>&limit=<limit>
    Returns (latency_ms, success_flag).
    """
    url = f"{base_url.rstrip('/')}/api/timeline"
    params = {"user": username, "limit": str(limit)}

    start = time.perf_counter()
    try:
        async with session.get(url, params=params) as resp:
            # We actually read the body so we measure full response time.
            await resp.text()
            ok = (resp.status == 200)
    except Exception:
        ok = False
    end = time.perf_counter()

    latency_ms = (end - start) * 1000.0
    return latency_ms, ok


async def run_one_config(
    base_url: str,
    usernames: List[str],
    limit: int,
) -> Tuple[float, int]:
    """
    Run one benchmark configuration:
      - one concurrent request per username (len(usernames) == concurrency)
      - returns (average_latency_ms, nb_failed_requests)
    """
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_timeline(session, base_url, u, limit)
            for u in usernames
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

    latencies = []
    failed = 0

    for r in results:
        if isinstance(r, Exception):
            failed += 1
            continue
        latency_ms, ok = r
        if not ok:
            failed += 1
        latencies.append(latency_ms)

    if latencies:
        avg_ms = sum(latencies) / len(latencies)
    else:
        avg_ms = float("nan")

    return avg_ms, failed


def make_usernames(prefix: str, count: int, start_index: int = 1) -> List[str]:
    """
    Generate 'count' distinct usernames: prefix + index.
    Example: prefix='user', count=3 -> ['user1', 'user2', 'user3'].
    Adjust prefix/start_index if your seed script used something else.
    """
    return [f"{prefix}{i}" for i in range(start_index, start_index + count)]


def main():
    parser = argparse.ArgumentParser(
        description="Exercice 1: concurrency benchmark for TinyInsta timeline."
    )
    parser.add_argument(
        "--base-url",
        default="https://cours-cloud-473712.ew.r.appspot.com",
        help="Base URL of your deployed app (no trailing slash).",
    )
    parser.add_argument(
        "--out",
        default="out/conc.csv",
        help="Path to CSV output file.",
    )
    parser.add_argument(
        "--user-prefix",
        default="user",
        help="Prefix of seeded usernames (e.g. 'user', 'demo', 'load').",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=1000,
        help="Total number of seeded users available.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Timeline limit parameter (GET /api/timeline?limit=<limit>).",
    )
    parser.add_argument(
        "--params",
        type=int,
        nargs="*",
        default=DEFAULT_PARAMS,
        help="Concurrency levels (number of simultaneous users).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per concurrency level.",
    )

    args = parser.parse_args()

    # Safety check
    if max(args.params) > args.max_users:
        raise SystemExit(
            f"Max concurrency {max(args.params)} is larger than max-users={args.max_users}."
        )

    # Ensure output directory exists
    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Open CSV and write header in UPPERCASE as requested
    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PARAM", "AVG_TIME", "RUN", "FAILED"])

        for param in args.params:
            for run_idx in range(1, args.runs + 1):
                # Use distinct users for this run: user1..userN, user(N+1).. etc is overkill,
                # the exercise only requires distinct users *within* a run, not across runs.
                usernames = make_usernames(args.user_prefix, param, start_index=1)

                print(
                    f"Running concurrency={param}, run={run_idx} "
                    f"against {args.base_url} ..."
                )

                avg_ms, failed = asyncio.run(
                    run_one_config(args.base_url, usernames, args.limit)
                )

                # FAILED column: 1 if any request failed, else 0
                failed_flag = 1 if failed > 0 else 0

                print(
                    f"  -> avg={avg_ms:.2f} ms, failed={failed}"
                )

                # Store avg latency in milliseconds as a numeric value (no 'ms' suffix)
                writer.writerow([param, f"{avg_ms:.2f}", run_idx, failed_flag])


if __name__ == "__main__":
    main()
