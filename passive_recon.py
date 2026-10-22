from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse
import requests
from collector import TargetValidationError

CT_URL = "https://crt.sh/"


def base_domain_from_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise TargetValidationError("Masukkan URL HTTPS yang valid.")
    host = p.hostname.lower().rstrip(".")
    if "." not in host or host == "localhost":
        raise TargetValidationError("Domain tidak valid.")
    # For safety, validate the explicitly supplied host resolves publicly.
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise TargetValidationError("Domain tidak dapat di-resolve.") from exc
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise TargetValidationError("Alamat nonpublik diblokir.")
    return host


def find_subdomains_passive(url: str, limit: int = 100) -> dict:
    """Passive certificate-transparency lookup only; does not probe discovered hosts."""
    domain = base_domain_from_url(url)
    limit = max(1, min(int(limit), 100))
    try:
        response = requests.get(
            CT_URL, params={"q": f"%.{domain}", "output": "json"},
            headers={"User-Agent": "LightweightOSINT-MVP/1.0"},
            timeout=12, allow_redirects=False,
        )
        response.raise_for_status()
        records = response.json()
        found = set()
        for record in records if isinstance(records, list) else []:
            for name in str(record.get("name_value", "")).splitlines():
                name = name.strip().lower().lstrip("*.").rstrip(".")
                if name == domain or name.endswith("." + domain):
                    found.add(name)
        return {
            "domain_queried": domain,
            "source": "crt.sh certificate transparency (passive)",
            "subdomains": sorted(found)[:limit],
            "count": min(len(found), limit),
            "note": "Sertifikat yang tercatat tidak membuktikan host masih aktif atau dimiliki pihak tertentu. Host tidak dipindai atau dihubungi.",
        }
    except Exception as exc:
        return {
            "domain_queried": domain, "source": "crt.sh certificate transparency (passive)",
            "subdomains": [], "count": 0,
            "error": type(exc).__name__,
            "note": "Lookup pasif gagal; periksa koneksi atau coba lagi nanti.",
        }
