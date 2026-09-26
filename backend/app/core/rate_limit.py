from slowapi import Limiter
from slowapi.util import get_remote_address

# Keyed on request.client.host, so it only sees real client IPs if the reverse proxy chain
# is set up to forward them (uvicorn's --forwarded-allow-ips). Counters live in process
# memory: fine for the single uvicorn worker this app runs, but they reset on restart and
# are not shared between workers.
limiter = Limiter(key_func=get_remote_address)
