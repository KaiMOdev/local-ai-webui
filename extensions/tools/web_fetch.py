"""
title: Web Fetch
author: webui
author_url: https://github.com/open-webui
version: 0.1.0
license: MIT
description: Haal een webpagina op en geef de leesbare tekst terug (voor "lees deze URL").
requirements: requests, beautifulsoup4
"""

# Open WebUI "Tool". Geeft het model de mogelijkheid de inhoud van een concrete
# URL op te halen en te lezen. Dit is iets anders dan web search: hier weet je de
# URL al (bv. de gebruiker plakt een link, of een ander resultaat verwijst ernaar).

import ipaddress
import re
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field


def _is_public_url(url: str) -> bool:
    """
    SSRF-bescherming: sta alleen http(s) naar publieke IP-adressen toe.
    Blokkeert loopback, private en link-local adressen (bv. cloud-metadata
    op 169.254.169.254) zodat een (prompt-geinjecteerd) model geen interne
    diensten kan benaderen. Let op: volgt het verzoek redirects, dus dit dekt
    de eerste host; voor strikte garantie kun je redirects uitschakelen.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


class Tools:
    class Valves(BaseModel):
        max_chars: int = Field(
            default=6000,
            description="Maximaal aantal tekens dat wordt teruggegeven (knipt lange pagina's af).",
        )
        timeout_seconds: int = Field(
            default=15, description="Time-out voor het HTTP-verzoek in seconden."
        )
        user_agent: str = Field(
            default="Mozilla/5.0 (compatible; OpenWebUI-WebFetch/0.1)",
            description="User-Agent header voor het verzoek.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def fetch_url(self, url: str, __event_emitter__=None) -> str:
        """
        Haal de inhoud van een webpagina op en geef de schone, leesbare tekst terug.
        Gebruik dit wanneer de gebruiker een specifieke URL noemt of wilt dat je een
        bepaalde pagina leest. Niet gebruiken voor algemeen 'zoeken op het web'.

        :param url: De volledige URL inclusief http:// of https://.
        :return: De leesbare tekst van de pagina (afgekapt), of een foutmelding.
        """
        url = url.strip()
        if not re.match(r"^https?://", url, re.IGNORECASE):
            return "Fout: geef een volledige URL op die begint met http:// of https://."
        if not _is_public_url(url):
            return (
                "Fout: deze URL wijst naar een niet-publiek of intern adres en wordt "
                "om veiligheidsredenen geweigerd."
            )

        async def _status(description: str, done: bool = False):
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": description, "done": done}}
                )

        await _status(f"Pagina ophalen: {url}")
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": self.valves.user_agent},
                timeout=self.valves.timeout_seconds,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            await _status("Ophalen mislukt", done=True)
            return f"Fout bij het ophalen van {url}: {e}"

        content_type = resp.headers.get("Content-Type", "")
        if "html" not in content_type and "text" not in content_type:
            await _status("Klaar", done=True)
            return f"De URL leverde geen tekst/HTML op (Content-Type: {content_type})."

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()

        title = (soup.title.string.strip() if soup.title and soup.title.string else url)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", soup.get_text("\n").strip())

        truncated = ""
        if len(text) > self.valves.max_chars:
            text = text[: self.valves.max_chars]
            truncated = "\n\n[... afgekapt ...]"

        await _status("Klaar", done=True)
        return f"# {title}\nBron: {url}\n\n{text}{truncated}"
