# SubsKeeper
SubKeeper — maniacally precise subdomain validator that keeps every host and IP. Never lose a sub, always validate, and get a complete, deduplicated view of your targets.

## Features

- Validate subdomains over HTTP/HTTPS without losing host↔IP associations  
- Filter by HTTP status codes  
- Collect response sizes and optionally deduplicate results  
- Works with proxies (HTTP/SOCKS5)  
- Domain-specific filtering  
- Quiet mode and trace ID tracking  
- Async, high-concurrency with `httpx` for speed  

## Installation

```bash
git clone https://github.com/yourusername/subkeeper.git
cd subkeeper
pip3 install -r requirements.txt
chmod +x subkeeper.py

