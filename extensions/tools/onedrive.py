"""
title: OneDrive (Microsoft Graph)
author: webui
author_url: https://github.com/open-webui
version: 0.1.0
license: MIT
description: Doorzoek en lees bestanden uit OneDrive via Microsoft Graph — on-demand 'live RAG' over je cloudopslag.
requirements: requests
"""

# Open WebUI "Tool" — cloud-connector voor OneDrive (Microsoft Graph).
#
# In plaats van LocalChat's achtergrond-sync naar een vector-DB, doet deze tool
# *on-demand retrieval*: het model roept search_files / list_recent_files aan om
# een bestand te vinden, en read_file om de tekst op te halen.
#
# === HERBRUIKBAAR BASIS-PATROON (kopieer dit voor SharePoint/Google Drive) ===
#   Valves      -> gedeelde app-registratie (tenant/client) + tuning (admin)
#   UserValves  -> per-gebruiker refresh_token (ieder z'n eigen account)
#   _get_access_token()  -> refresh-token => access-token (met in-memory cache)
#   _graph_get()         -> geauthenticeerde API-call
#   _extract_text()      -> bytes => tekst (txt/md/csv/json/docx/pdf)
# SharePoint en Google Drive volgen exact dezelfde vorm; alleen de endpoints
# en de scope/token-URL verschillen.
#
# === EENMALIGE SETUP (Azure AD) ===
#   1. Azure Portal -> App registrations -> New registration (single tenant of
#      'common' voor persoonlijke accounts). Voeg een redirect-URI toe.
#   2. API permissions -> Microsoft Graph -> Delegated: Files.Read.All,
#      Sites.Read.All, offline_access. Grant admin consent indien nodig.
#   3. Certificates & secrets -> nieuw client secret.
#   4. Admin vult in de Valves: tenant_id, client_id, client_secret.
#   5. Elke gebruiker haalt eenmalig een refresh_token op (auth-code flow) en
#      zet dit in zijn UserValves. Zie extensions/README.md voor een kort script.

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import requests
from pydantic import BaseModel, Field

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_SCOPE = "Files.Read.All Sites.Read.All offline_access"

# Bestandstypen die we als platte tekst kunnen teruggeven.
_TEXT_EXT = {"txt", "md", "markdown", "csv", "json", "log", "xml", "html", "htm", "yml", "yaml"}


class Tools:
    class Valves(BaseModel):
        tenant_id: str = Field(default="common", description="Azure AD tenant ID, of 'common'.")
        client_id: str = Field(default="", description="Client ID van de Azure AD app-registratie.")
        client_secret: str = Field(
            default="", description="Client secret van de app-registratie."
        )
        max_chars: int = Field(default=6000, description="Max. tekens per bestand bij read_file.")
        timeout_seconds: int = Field(default=30, description="HTTP time-out in seconden.")

    class UserValves(BaseModel):
        refresh_token: str = Field(
            default="",
            description="Jouw persoonlijke OAuth refresh token (delegated, met offline_access).",
        )

    def __init__(self):
        self.valves = self.Valves()
        # refresh_token -> {"access_token": str, "expires_at": datetime}
        self._token_cache: dict = {}

    # ----- herbruikbare basis-helpers ------------------------------------------
    def _get_access_token(self, __user__: dict | None) -> str:
        uv = (__user__ or {}).get("valves")
        refresh_token = getattr(uv, "refresh_token", "") if uv else ""
        if not refresh_token:
            raise RuntimeError(
                "Geen refresh_token ingesteld in je UserValves. Zie de setup in de tool-beschrijving."
            )
        if not self.valves.client_id:
            raise RuntimeError(
                "Admin moet tenant_id/client_id/client_secret instellen in de Valves."
            )

        cached = self._token_cache.get(refresh_token)
        if cached and datetime.now(UTC) < cached["expires_at"]:
            return cached["access_token"]

        url = _TOKEN_URL.format(tenant=self.valves.tenant_id or "common")
        resp = requests.post(
            url,
            data={
                "grant_type": "refresh_token",
                "client_id": self.valves.client_id,
                "client_secret": self.valves.client_secret,
                "refresh_token": refresh_token,
                "scope": _SCOPE,
            },
            timeout=self.valves.timeout_seconds,
        )
        if not resp.ok:
            raise RuntimeError(f"Token-refresh mislukt: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_cache[refresh_token] = {
            "access_token": access_token,
            "expires_at": datetime.now(UTC) + timedelta(seconds=max(60, expires_in - 60)),
        }
        return access_token

    def _graph_get(self, path: str, __user__: dict | None, **kwargs) -> requests.Response:
        token = self._get_access_token(__user__)
        url = path if path.startswith("http") else f"{_GRAPH_BASE}{path}"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.valves.timeout_seconds,
            **kwargs,
        )
        resp.raise_for_status()
        return resp

    @staticmethod
    def _extract_text(name: str, content: bytes, max_chars: int) -> str:
        suffix = name.lower().rsplit(".", 1)[-1] if "." in name else ""
        text = ""
        if suffix in _TEXT_EXT:
            text = content.decode("utf-8", errors="replace")
        elif suffix == "docx":
            try:
                import io

                from docx import Document  # python-docx (door Open WebUI gebundeld)

                text = "\n".join(p.text for p in Document(io.BytesIO(content)).paragraphs)
            except Exception as e:
                return f"(Kon .docx niet lezen: {e})"
        elif suffix == "pdf":
            try:
                import io

                from pypdf import PdfReader  # door Open WebUI gebundeld

                reader = PdfReader(io.BytesIO(content))
                text = "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception as e:
                return f"(Kon .pdf niet lezen: {e})"
        else:
            return f"(Bestandstype '.{suffix}' wordt niet als tekst ondersteund; {len(content)} bytes.)"

        text = text.strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[... afgekapt ...]"
        return text or "(Leeg of geen extraheerbare tekst.)"

    # ----- LLM-aanroepbare tools -----------------------------------------------
    def search_files(self, query: str, limit: int = 10, __user__: dict | None = None) -> str:
        """
        Zoek bestanden in OneDrive op naam of inhoud via Microsoft Graph.
        Gebruik dit om de file-id te vinden vóórdat je read_file aanroept.

        :param query: Zoekterm (bestandsnaam of inhoud).
        :param limit: Max. aantal resultaten (standaard 10).
        :return: Lijst met bestandsnaam, id, type en wijzigingsdatum, of een foutmelding.
        """
        safe = quote(query.replace("'", " "))
        top = max(1, min(limit, 25))
        try:
            resp = self._graph_get(
                f"/me/drive/root/search(q='{safe}')?$top={top}", __user__
            )
            items = resp.json().get("value", [])
        except Exception as e:
            return f"Fout bij zoeken in OneDrive: {e}"
        if not items:
            return f"Geen bestanden gevonden voor '{query}'."
        lines = [f"Gevonden bestanden voor '{query}':"]
        for it in items:
            kind = "map" if "folder" in it else "bestand"
            lines.append(
                f"- {it.get('name')} [{kind}] | id={it.get('id')} | "
                f"gewijzigd={it.get('lastModifiedDateTime', '?')}"
            )
        return "\n".join(lines)

    def list_recent_files(self, limit: int = 10, __user__: dict | None = None) -> str:
        """
        Toon recent geopende OneDrive-bestanden (handig als de gebruiker 'mijn laatste document' bedoelt).

        :param limit: Max. aantal resultaten (standaard 10).
        :return: Lijst met recente bestanden (naam + id), of een foutmelding.
        """
        try:
            items = self._graph_get("/me/drive/recent", __user__).json().get("value", [])
        except Exception as e:
            return f"Fout bij ophalen van recente bestanden: {e}"
        items = items[: max(1, min(limit, 25))]
        if not items:
            return "Geen recente bestanden gevonden."
        return "Recente bestanden:\n" + "\n".join(
            f"- {it.get('name')} | id={it.get('id')}" for it in items
        )

    def read_file(self, item_id: str, __user__: dict | None = None) -> str:
        """
        Lees de tekstinhoud van een OneDrive-bestand op basis van zijn id.
        Vraag eerst search_files of list_recent_files om het id te vinden.
        Ondersteunt txt/md/csv/json/yaml/html en (indien beschikbaar) docx/pdf.

        :param item_id: De Microsoft Graph item-id van het bestand.
        :return: De (afgekapte) tekstinhoud met bron-URL, of een foutmelding.
        """
        try:
            meta = self._graph_get(f"/me/drive/items/{item_id}", __user__).json()
            name = meta.get("name", "bestand")
            content = self._graph_get(
                f"/me/drive/items/{item_id}/content", __user__, allow_redirects=True
            ).content
        except Exception as e:
            return f"Fout bij het lezen van bestand {item_id}: {e}"
        text = self._extract_text(name, content, self.valves.max_chars)
        return f"# {name}\nBron: {meta.get('webUrl', '')}\n\n{text}"
