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


## TODO
Use massnds file as input, while waiting you can convert a it with following command:
awk '$2=="CNAME"{c[$1]=$3} $2=="A"{ip[$1]=$3} END{for(h in c){x=h; while(x in c)x=c[x]; if(x in ip)print h, ip[x]} for(h in ip)print h, ip[h]}' massdns_output_file.raw | sed 's/\.$//g' | sort -u  >subs_host_ip.txt

