#!/usr/bin/env python3
import asyncio
import aiohttp
import time
import csv
import os
import argparse
from typing import List, Tuple

DEFAULT_PARAMS = [10, 50, 100]   # followees per user
DEFAULT_CONCURRENCY = 50         # fixed by the assignment


async def fetch_timeline(session, base_url, username, limit):
    url = f"{base_url.rstrip('/')}/api/timeline"
    params = {"user": username, "limit": str(limit)}

    start = time.perf_counter()
    try:
        async with session.get(url, params=params) as resp:
            await resp.text()
            ok = (resp.status == 200)
    except Exception:
        ok = False
    end = time.perf_counter()

    latency_ms = (end - start) * 1000.0
    return latency_ms, ok


async def run_one_config(base_url, usernames, limit):
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


def make_usernames(prefix, count, start_index=1):
    return [f"{prefix}{i}" for i in range(start_index, start_index + count)]


def main():
    parser = argparse.ArgumentParser(
        description="Exercice 2 (fanout): benchmark with varying followees per user."
    )
    parser.add_argument(
        "--base-url",
        default="https://cours-cloud-473712.ew.r.appspot.com",
        help="Base URL of your deployed app.",
    )
    parser.add_argument(
        "--out",
        default="out/fanout.csv",
        help="Path to CSV output file.",
    )
    parser.add_argument(
        "--user-prefix",
        default="user",
        help="Prefix of seeded usernames.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Timeline limit parameter.",
    )
    parser.add_argument(
        "--params",
        type=int,
        nargs="*",
        default=DEFAULT_PARAMS,
        help="Values of PARAM = followees per user.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per parameter value.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="Number of simultaneous users (fixed = 50).",
    )

    args = parser.parse_args()

    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    write_header = not os.path.exists(args.out)
    mode = "a" if not write_header else "w"

    with open(args.out, mode, newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["PARAM", "AVG_TIME", "RUN", "FAILED"])

        for param in args.params:
            for run_idx in range(1, args.runs + 1):
                usernames = make_usernames(args.user_prefix, args.concurrency, 1)

                print(
                    f"[FANOUT] PARAM={param} (followees/user), run={run_idx}, "
                    f"concurrency={args.concurrency}"
                )

                avg_ms, failed = asyncio.run(
                    run_one_config(args.base_url, usernames, args.limit)
                )

                failed_flag = 1 if failed > 0 else 0
                print(f"  -> avg={avg_ms:.2f} ms, failed={failed}")

                writer.writerow([param, f"{avg_ms:.2f}", run_idx, failed_flag])


if __name__ == "__main__":
    main()
