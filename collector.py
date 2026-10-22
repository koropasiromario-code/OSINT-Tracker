from __future__ import annotations
import ipaddress
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

MAX_RESPONSE_BYTES = 1_000_000
TIMEOUT_SECONDS = 8
MAX_PAGES = 15
USER_AGENT = "LightweightOSINT-MVP/1.0 (authorized public asset inventory)"


class TargetValidationError(ValueError):
    pass


def _public_host(host: str) -> None:
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise TargetValidationError("Domain tidak dapat di-resolve.") from exc
    if not answers:
        raise TargetValidationError("Domain tidak memiliki alamat DNS.")
    for answer in answers:
        try:
            ip = ipaddress.ip_address(answer[4][0])
        except ValueError as exc:
            raise TargetValidationError("Alamat DNS tidak valid.") from exc
        if not ip.is_global:
            raise TargetValidationError("Domain resolve ke alamat IP nonpublik; permintaan diblokir.")


def normalize_target(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise TargetValidationError("Masukkan URL HTTPS yang valid.")
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise TargetValidationError("Hanya URL HTTPS yang diperbolehkan.")
    if parsed.username or parsed.password:
        raise TargetValidationError("URL berisi kredensial tidak diperbolehkan.")
    if parsed.port not in (None, 443):
        raise TargetValidationError("Hanya port HTTPS standar (443) yang diperbolehkan.")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost") or "." not in host:
        raise TargetValidationError("Nama host ini tidak diperbolehkan.")
    _public_host(host)
    path = parsed.path or "/"
    return f"https://{host}{path}" + (f"?{parsed.query}" if parsed.query else "")


def _fetch_html(url: str):
    safe_url = normalize_target(url)
    # No redirects: prevents redirect-based SSRF. Production should also enforce
    # outbound network restrictions at the hosting/firewall layer.
    with requests.get(
        safe_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS,
        allow_redirects=False, stream=True,
    ) as response:
        if 300 <= response.status_code < 400:
            return safe_url, response.status_code, response.headers, ""
        response.raise_for_status()
        ctype = response.headers.get("Content-Type", "")
        if "text/html" not in ctype.lower():
            return safe_url, response.status_code, response.headers, ""
        chunks, total = [], 0
        for chunk in response.iter_content(chunk_size=16384):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise TargetValidationError("Respons melebihi batas 1 MB.")
            chunks.append(chunk)
        body = b"".join(chunks)
        encoding = response.encoding or "utf-8"
        return safe_url, response.status_code, response.headers, body.decode(encoding, errors="replace")


def _page_metadata(url: str, status: int, headers, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    def meta(name=None, prop=None):
        tag = soup.find("meta", attrs={"name": name}) if name else None
        if tag is None and prop:
            tag = soup.find("meta", attrs={"property": prop})
        return (tag.get("content") or "").strip() if tag else None
    title = soup.find("title")
    tech_hints = []
    generator = meta(name="generator")
    if generator:
        tech_hints.append({"technology": generator, "evidence": "meta generator"})
    powered = headers.get("X-Powered-By")
    if powered:
        tech_hints.append({"technology": powered, "evidence": "X-Powered-By header"})
    server = headers.get("Server")
    if server:
        tech_hints.append({"technology": server, "evidence": "Server header"})
    html_lower = html.lower()
    for marker, label in [
        ("wp-content/", "WordPress"),
        ("cdn.shopify.com", "Shopify"),
        ("__next_data__", "Next.js"),
        ("data-reactroot", "React"),
        ("ng-version=", "Angular"),
        ("_nuxt/", "Nuxt"),
    ]:
        if marker in html_lower and not any(x["technology"] == label for x in tech_hints):
            tech_hints.append({"technology": label, "evidence": f"HTML marker: {marker}"})
    return {
        "url": url, "status_code": status,
        "title": title.get_text(" ", strip=True) if title else None,
        "description": meta(name="description"),
        "canonical": (soup.find("link", rel="canonical").get("href")
                      if soup.find("link", rel="canonical") else None),
        "meta_robots": meta(name="robots"),
        "og_title": meta(prop="og:title"),
        "og_description": meta(prop="og:description"),
        "content_type": headers.get("Content-Type"),
        "server_header": server,
        "technology_hints": tech_hints,
    }, soup


def collect_site(url: str, max_pages: int = MAX_PAGES) -> dict:
    start = normalize_target(url)
    base = urlparse(start)
    base_host = base.hostname
    max_pages = max(1, min(int(max_pages), MAX_PAGES))
    queue, seen, pages, errors = [start], set(), [], []
    while queue and len(pages) < max_pages:
        current = urldefrag(queue.pop(0))[0]
        if current in seen:
            continue
        parsed = urlparse(current)
        if parsed.scheme != "https" or parsed.hostname != base_host:
            continue
        seen.add(current)
        try:
            safe, status, headers, html = _fetch_html(current)
            page, soup = _page_metadata(safe, status, headers, html)
            pages.append(page)
            if html:
                for a in soup.find_all("a", href=True):
                    candidate = urldefrag(urljoin(safe, a["href"].strip()))[0]
                    p = urlparse(candidate)
                    if p.scheme == "https" and p.hostname == base_host and candidate not in seen and candidate not in queue:
                        if not p.username and not p.password and p.port in (None, 443):
                            queue.append(candidate)
                            if len(queue) >= MAX_PAGES * 3:
                                break
        except Exception as exc:
            # Keep errors minimal; don't expose request internals or secrets.
            errors.append({"url": current, "error": type(exc).__name__})
    first = pages[0] if pages else {}
    return {
        "target": start,
        "base_domain": base_host,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "pages_scanned": len(pages),
        "pages": pages,
        "crawl_errors": errors[:MAX_PAGES],
        "technology_hints": _unique_hints(pages),
        "limitations": [
            "Crawl dibatasi ke host yang sama dan maksimum 15 halaman.",
            "Hanya HTTPS port 443; redirect tidak diikuti.",
            "Petunjuk teknologi bersifat indikatif, bukan bukti pasti.",
        ],
        "title": first.get("title"),
        "description": first.get("description"),
        "status_code": first.get("status_code"),
        "content_type": first.get("content_type"),
        "server_header": first.get("server_header"),
    }


def _unique_hints(pages):
    seen, out = set(), []
    for page in pages:
        for hint in page.get("technology_hints", []):
            key = (hint.get("technology"), hint.get("evidence"))
            if key not in seen:
                seen.add(key)
                out.append(hint)
    return out
