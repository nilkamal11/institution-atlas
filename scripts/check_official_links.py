import argparse
import concurrent.futures
import html
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
parser = argparse.ArgumentParser()
parser.add_argument("--record", action="store_true")
args = parser.parse_args()

urls = set()
for page in DOCS.glob("*.html"):
    text = page.read_text(encoding="utf-8")
    urls.update(html.unescape(url) for url in re.findall(r'href="(https://[^"#]+)', text))

context = ssl.create_default_context()


def check(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 InstitutionAtlasLinkCheck/1.0", "Accept": "text/html,application/json,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=25, context=context) as response:
            return {"url": url, "status": response.status, "result": "resolved", "final_url": response.geturl()}
    except urllib.error.HTTPError as error:
        result = "restricted" if error.code in {401, 403, 405, 406, 409, 429} else "broken" if error.code in {404, 410} else "unverified"
        return {"url": url, "status": error.code, "result": result, "error": str(error.reason)}
    except Exception as error:
        message = str(error)
        result = "broken" if "redirect" in message.lower() else "unverified"
        return {"url": url, "status": None, "result": result, "error": message[:240]}


with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    rows = list(pool.map(check, sorted(urls)))

report = {
    "schema_version": "1.0.0",
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "total": len(rows),
    "resolved_count": sum(row["result"] == "resolved" for row in rows),
    "restricted_count": sum(row["result"] == "restricted" for row in rows),
    "unverified_count": sum(row["result"] == "unverified" for row in rows),
    "broken_count": sum(row["result"] == "broken" for row in rows),
    "broken": [row for row in rows if row["result"] == "broken"],
    "results": rows,
}
if args.record:
    (ROOT / "data" / "link-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: report[key] for key in ["checked_at", "total", "resolved_count", "restricted_count", "unverified_count", "broken_count"]}, indent=2))
if report["broken_count"]:
    raise SystemExit(2)
