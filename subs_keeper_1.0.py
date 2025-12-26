#!/usr/bin/env python3
import argparse
import asyncio
from typing import List, Set
import httpx
import random
import string

TRACE_HEADER_NAME = "X-" + "".join(
    random.choices(string.ascii_uppercase + string.digits, k=8)
)

# -------------------------
# Input parsing
# -------------------------

def parse_input(path: str) -> List[tuple[str, str]]:
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            entries.append((parts[0], parts[1]))
    return entries

def parse_status_codes(mc: str | None) -> Set[int] | None:
    if not mc:
        return None
    codes: Set[int] = set()
    for part in mc.split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            codes.update(range(int(start), int(end) + 1))
        else:
            codes.add(int(part))
    return codes

# -------------------------
# Fetch logic
# -------------------------

async def fetch(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    host: str,
    ip: str,
    scheme: str,
    valid_codes: Set[int] | None,
):
    trace_value = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    
    headers = {
        "Host": host,
        TRACE_HEADER_NAME: trace_value,
    }

    # Use extensions for SNI while connecting to IP
    extensions = {"sni_hostname": host} if scheme == "https" else {}

    async with sem:
        try:
            r = await client.get(
                f"{scheme}://{ip}",
                headers=headers,
                extensions=extensions,
                follow_redirects=False,
            )

            size = len(r.content)
            if valid_codes is None or r.status_code in valid_codes:
                return host, ip, scheme, r.status_code, size, trace_value
        except Exception:
            return None
    return None

# -------------------------
# Runner
# -------------------------

async def run(entries, concurrency: int, valid_codes: Set[int] | None, proxy):
    # Create semaphore inside the loop to avoid loop mismatch errors
    sem = asyncio.Semaphore(concurrency)
    
    async with httpx.AsyncClient(
        proxy=proxy,
        verify=False, # Required for direct IP connection with SNI override
        timeout=10.0,
        limits=httpx.Limits(max_connections=concurrency)
    ) as client:

        tasks = [
            fetch(client, sem, host, ip, scheme, valid_codes)
            for host, ip in entries
            for scheme in ("http", "https")
        ]

        results = []
        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res:
                results.append(res)
    return results

# -------------------------
# Output formatting
# -------------------------

def format_line(host, ip, scheme, code, size, trace, args):
    if args.quiet:
        return f"{host} {ip}"

    line = f"{scheme}://{host} {ip}"
    if args.sc:
        line += f" [{code}]"
    if args.size:
        line += f" [size={size}]"
    if args.id:
        line += f" [{TRACE_HEADER_NAME}:{trace}]"
    return line

# -------------------------
# Main
# -------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="subs_validator",
        description=(
            "Validate subdomain URLs over HTTP/HTTPS using httpx\n"
            "while preserving the original Host header and HTTPS SNI.\n\n"
            "Input format:\n"
            "  <hostname> <ip>\n"
            "Example:\n"
            "  www.example.com 1.2.3.4"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("input", help="Input file with lines: <hostname> <ip>")
    
    filtering = parser.add_argument_group("Filtering")
    filtering.add_argument("-d", "--domain", help="Filter hostnames by domain")
    filtering.add_argument("-mc", help="Match HTTP status codes")

    output = parser.add_argument_group("Output control")
    output.add_argument("-q", "--quiet", action="store_true")
    output.add_argument("-sc", action="store_true")
    output.add_argument("--size", action="store_true")
    output.add_argument("--id", action="store_true")

    post = parser.add_argument_group("Post-processing")
    post.add_argument("--sort-size", action="store_true", help="Sort results by response size")
    post.add_argument("--dedup-size", action="store_true", help="Deduplicate results by response size")
    post.add_argument("--min-dedup-size", type=int, default=200, help="Minimum size to apply deduplication")

    network = parser.add_argument_group("Networking")
    network.add_argument("-t", "--threads", type=int, default=50)
    network.add_argument("-p", "--proxy", default=None)

    args = parser.parse_args()
    entries = parse_input(args.input)

    if args.domain:
        entries = [(h, ip) for h, ip in entries if args.domain.lower() in h.lower()]

    if not entries:
        print("No entries to process.")
        return

    valid_codes = parse_status_codes(args.mc)
    results = asyncio.run(run(entries, args.threads, valid_codes, args.proxy))

    # Deduplication logic (only if size >= min-dedup-size)
    if args.dedup_size:
        unique_results = {}
        processed = []
        for res in results:
            size = res[4]
            if size >= args.min_dedup_size:
                if size not in unique_results:
                    unique_results[size] = res
                    processed.append(res)
            else:
                processed.append(res)
        results = processed

    # Sorting logic
    if args.sort_size:
        results.sort(key=lambda x: x[4])

    for res in results:
        print(format_line(*res, args))

if __name__ == "__main__":
    main()
