# utils.py
import urllib.error
import urllib.request

from scripts.config import HEADERS

_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", HEADERS["User-Agent"])]


def get(url):
    try:
        with _opener.open(url, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} for {url}")
        raise


def find_text(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None


def to_bool(v):
    return v in ("1", "true")
