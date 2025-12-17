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


async def fetch(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    host: str,
    ip: str,
    scheme: str,
    valid_codes: Set[int] | None,
):
    trace_value = "".join(
        random.choices(string.ascii_lowercase + string.digits, k=12)
    )

    headers = {
        "Host": host,
        TRACE_HEADER_NAME: trace_value,
    }

    async with sem:
        try:
            r = await client.get(
                f"{scheme}://{ip}",
                headers=headers,
                follow_redirects=True,
                timeout=10.0,
            )
            size = len(r.content)
            if valid_codes is None or r.status_code in valid_codes:
                return host, ip, scheme, r.status_code, size, trace_value
        except Exception:
            return None
    return None


async def run(entries, concurrency: int, valid_codes: Set[int] | None, proxy):
    sem = asyncio.Semaphore(concurrency)
    results = []

    async with httpx.AsyncClient(verify=False, proxy=proxy) as client:
        tasks = [
            fetch(client, sem, host, ip, scheme, valid_codes)
            for host, ip in entries
            for scheme in ("http", "https")
        ]

        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res:
                results.append(res)

    return results


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


def main():
    parser = argparse.ArgumentParser(
        prog="subs_validator",
        description=(
            "Validate subdomain URLs over HTTP/HTTPS using httpx\n"
            "while preserving the original Host header.\n\n"
            "Input format:\n"
            "  <hostname> <ip>\n"
            "Example:\n"
            "  www.example.com 1.2.3.4"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Required argument
    parser.add_argument("input", help="Input file with lines: <hostname> <ip>")

    # Filtering group
    filtering = parser.add_argument_group("Filtering")
    filtering.add_argument(
        "-d", "--domain",
        help="Keep only hostnames containing this domain (e.g. tesla.com)"
    )
    filtering.add_argument(
        "-mc",
        help="Match HTTP status codes (e.g. 200,301,302 or 200-499)"
    )

    # Output control
    output = parser.add_argument_group("Output control")
    output.add_argument("-q", "--quiet", action="store_true", help="Print only hostname and IP")
    output.add_argument("-sc", action="store_true", help="Print HTTP status code")
    output.add_argument("--size", action="store_true", help="Print response size in bytes")
    output.add_argument("--id", action="store_true", help="Print trace ID header. Useful to track the request in proxies like burp/zap history")

    # Post-processing
    post = parser.add_argument_group("Post-processing")
    post.add_argument("--sort-size", action="store_true", help="Sort results by response size")
    post.add_argument("--dedup-size", action="store_true", help="Deduplicate results by response size")
    post.add_argument(
        "--min-dedup-size",
        type=int,
        default=200,
        help="Minimum size for deduplication (default: 200)"
    )

    # Networking
    network = parser.add_argument_group("Networking")
    network.add_argument("-t", "--threads", type=int, default=50, help="Concurrency level (default: 50)")
    network.add_argument("-p", "--proxy", default=None, help="Proxy URL (http://127.0.0.1:8080, socks5://127.0.0.1:9050)")

    # Examples
    parser.epilog = (
        "Examples:\n"
        "  # Minimal output\n"
        "  subs_validator input.txt -q\n\n"
        "  # Filter by domain and status code\n"
        "  subs_validator input.txt -d example.com -mc 200-399\n\n"
        "  # Sort by response size and remove duplicates\n"
        "  subs_validator input.txt --sort-size --dedup-size\n\n"
        "  # Through proxy with tracing id\n"
        "  subs_validator input.txt -p http://127.0.0.1:8080" --id
    )

    args = parser.parse_args()

    entries = parse_input(args.input)

    # Domain filter
    if args.domain:
        entries = [(h, ip) for h, ip in entries if args.domain.lower() in h.lower()]

    if not entries:
        print("No entries to process after filtering.")
        return

    valid_codes = parse_status_codes(args.mc)
    defer_print = args.sort_size or args.dedup_size

    results = asyncio.run(run(entries, args.threads, valid_codes, args.proxy))

    seen = set()
    collected = []

    for host, ip, scheme, code, size, trace in results:
        key = (host, ip)
        if key in seen:
            continue
        seen.add(key)
        collected.append((host, ip, scheme, code, size, trace))

        if not defer_print:
            print(format_line(host, ip, scheme, code, size, trace, args))

    if defer_print:
        if args.sort_size:
            collected.sort(key=lambda x: x[4])

        seen_sizes = set()
        for host, ip, scheme, code, size, trace in collected:
            if args.dedup_size and size >= args.min_dedup_size:
                if size in seen_sizes:
                    continue
                seen_sizes.add(size)

            print(format_line(host, ip, scheme, code, size, trace, args))


if __name__ == "__main__":
    main()
