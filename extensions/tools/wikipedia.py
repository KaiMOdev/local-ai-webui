"""
title: Wikipedia
author: webui
author_url: https://github.com/open-webui
version: 0.1.0
license: MIT
description: Zoek op Wikipedia en haal een samenvatting van een artikel op.
requirements: requests
"""

# Open WebUI "Tool". Twee methodes: zoeken naar pagina's en een samenvatting
# ophalen. Gebruikt de publieke Wikipedia REST/Action API (geen API-key nodig).

import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        language: str = Field(
            default="nl",
            description="Wikipedia-taalcode, bv. 'nl', 'en', 'fr', 'de'.",
        )
        timeout_seconds: int = Field(default=15, description="HTTP time-out in seconden.")

    def __init__(self):
        self.valves = self.Valves()

    def _api(self) -> str:
        return f"https://{self.valves.language}.wikipedia.org/w/api.php"

    def search_wikipedia(self, query: str, limit: int = 5) -> str:
        """
        Zoek op Wikipedia naar pagina's die bij een zoekterm passen.
        Gebruik dit om de juiste paginatitel te vinden voordat je een samenvatting opvraagt.

        :param query: De zoekterm.
        :param limit: Maximaal aantal resultaten (standaard 5).
        :return: Een lijst met paginatitels en korte fragmenten, of een foutmelding.
        """
        try:
            resp = requests.get(
                self._api(),
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max(1, min(limit, 10)),
                    "format": "json",
                },
                timeout=self.valves.timeout_seconds,
            )
            resp.raise_for_status()
            hits = resp.json().get("query", {}).get("search", [])
        except Exception as e:
            return f"Fout bij het zoeken op Wikipedia: {e}"

        if not hits:
            return f"Geen Wikipedia-resultaten gevonden voor '{query}'."

        lines = [f"Resultaten voor '{query}' ({self.valves.language}.wikipedia.org):"]
        for h in hits:
            snippet = (
                h.get("snippet", "")
                .replace('<span class="searchmatch">', "")
                .replace("</span>", "")
            )
            lines.append(f"- {h.get('title')}: {snippet}")
        return "\n".join(lines)

    def get_summary(self, title: str, sentences: int = 5) -> str:
        """
        Haal een tekstsamenvatting (intro) van een Wikipedia-artikel op.
        Gebruik de exacte paginatitel, eventueel eerst gevonden via search_wikipedia.

        :param title: De exacte titel van het Wikipedia-artikel.
        :param sentences: Aantal zinnen van de intro (1-10, standaard 5).
        :return: De samenvatting met bron-URL, of een foutmelding.
        """
        try:
            resp = requests.get(
                self._api(),
                params={
                    "action": "query",
                    "prop": "extracts",
                    "exintro": 1,
                    "explaintext": 1,
                    "exsentences": max(1, min(sentences, 10)),
                    "redirects": 1,
                    "titles": title,
                    "format": "json",
                },
                timeout=self.valves.timeout_seconds,
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
        except Exception as e:
            return f"Fout bij het ophalen van de samenvatting: {e}"

        page = next(iter(pages.values()), {})
        extract = page.get("extract", "").strip()
        if not extract:
            return (
                f"Geen samenvatting gevonden voor '{title}'. "
                f"Probeer eerst search_wikipedia om de juiste titel te vinden."
            )

        page_title = page.get("title", title)
        url = f"https://{self.valves.language}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
        return f"# {page_title}\nBron: {url}\n\n{extract}"
