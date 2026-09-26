"""Process liveness only; no provider/DB reads or private error output."""

import json
import os
import sys
import urllib.request


def main():
    try:
        port = int(os.getenv("AGENT_HTTP_PORT", "8768"))
        url = f"http://127.0.0.1:{port}/healthz"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=2) as response:
            ok = response.status == 200 and json.loads(response.read(1024)).get("alive") is True
    except Exception:
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
