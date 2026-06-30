"""
title: Research Agent
author: webui
author_url: https://github.com/open-webui
version: 0.1.0
license: MIT
description: Een Pipe (skill/agent) die web search via SearXNG combineert met een lokaal model en een onderbouwd antwoord met bronnen geeft.
requirements: requests
"""

# Open WebUI "Function" van het type Pipe. Een Pipe verschijnt als een eigen
# "model" in de modelkiezer. Deze agent doet, los van de gewone chat, een
# meerstaps-workflow:
#   1) zoekt op het web via de interne SearXNG-service,
#   2) verzamelt de beste resultaten (titels + snippets, optioneel volledige tekst),
#   3) laat het lokale Ollama-model een antwoord met bronvermelding schrijven.

import os

import requests
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        ollama_base_url: str = Field(
            default=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
            description="Basis-URL van Ollama.",
        )
        model: str = Field(
            default="qwen2.5:7b-instruct",
            description="Ollama-model voor de synthese (moet gepulld zijn).",
        )
        searxng_url: str = Field(
            default="http://searxng:8080/search",
            description="Interne SearXNG zoek-endpoint (Docker-netwerknaam).",
        )
        num_results: int = Field(default=4, description="Aantal zoekresultaten dat wordt gebruikt.")
        fetch_pages: bool = Field(
            default=False,
            description="Volledige pagina-inhoud ophalen i.p.v. alleen snippets (trager, rijker).",
        )
        max_page_chars: int = Field(default=2500, description="Max. tekens per opgehaalde pagina.")

    def __init__(self):
        self.name = "Research Agent"
        self.valves = self.Valves()

    # --- helpers -----------------------------------------------------------------
    def _search(self, query: str) -> list[dict]:
        resp = requests.get(
            self.valves.searxng_url,
            params={"q": query, "format": "json"},
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[: self.valves.num_results]

    def _fetch(self, url: str) -> str:
        try:
            from bs4 import BeautifulSoup

            r = requests.get(
                url, headers={"User-Agent": "OpenWebUI-ResearchAgent/0.1"}, timeout=15
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for t in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                t.decompose()
            return soup.get_text(" ", strip=True)[: self.valves.max_page_chars]
        except Exception:
            return ""

    async def pipe(self, body: dict, __event_emitter__=None) -> str:
        async def status(desc: str, done: bool = False):
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": desc, "done": done}}
                )

        messages = body.get("messages", [])
        query = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        ).strip()
        if not query:
            return "Stel een onderzoeksvraag om de Research Agent te gebruiken."

        # 1) Web search
        await status(f"Zoeken op het web: {query}")
        try:
            results = self._search(query)
        except Exception as e:
            return (
                f"Web search via SearXNG mislukte ({e}). "
                f"Controleer of de searxng-container draait en JSON-output aan staat."
            )
        if not results:
            return f"Geen zoekresultaten gevonden voor '{query}'."

        # 2) Context verzamelen
        sources, context_blocks = [], []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Zonder titel")
            url = r.get("url", "")
            snippet = r.get("content", "")
            sources.append(f"[{i}] {title} — {url}")
            body_text = snippet
            if self.valves.fetch_pages and url:
                await status(f"Bron {i}/{len(results)} ophalen…")
                page = self._fetch(url)
                if page:
                    body_text = page
            context_blocks.append(f"[{i}] {title} ({url})\n{body_text}")

        context = "\n\n".join(context_blocks)
        sources_list = "\n".join(sources)

        # 3) Synthese door het lokale model
        await status("Antwoord samenstellen met bronnen…")
        system_prompt = (
            "Je bent een nauwkeurige onderzoeksassistent. Beantwoord de vraag uitsluitend "
            "op basis van de aangeleverde bronnen. Verwijs naar bronnen met [n]-markeringen. "
            "Als de bronnen het antwoord niet bevatten, zeg dat eerlijk. Antwoord in de taal "
            "van de vraag."
        )
        user_prompt = f"Vraag: {query}\n\nBronnen:\n{context}"

        try:
            resp = requests.post(
                f"{self.valves.ollama_base_url}/api/chat",
                json={
                    "model": self.valves.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                },
                timeout=180,
            )
            resp.raise_for_status()
            answer = resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            return f"Fout bij het genereren van het antwoord met model '{self.valves.model}': {e}"

        await status("Klaar", done=True)
        return f"{answer}\n\n---\n**Bronnen**\n{sources_list}"
