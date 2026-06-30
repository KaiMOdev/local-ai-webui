"""
title: Prompt Enhancer
author: webui
author_url: https://github.com/open-webui
version: 0.1.0
license: MIT
description: Een Filter die elke prompt verrijkt met actuele context (datum/tijd) en lichte normalisatie.
requirements:
"""

# Open WebUI "Function" van het type Filter. Een Filter draait rond elke chat:
#   - inlet():  past het verzoek aan vóór het naar het model gaat
#   - outlet(): kan het antwoord nabewerken nadat het model klaar is
# Hier injecteren we de huidige datum/tijd als systeemcontext, zodat het model
# "vandaag", "deze week" enz. correct interpreteert. Het lost ook het bekende
# probleem op dat lokale modellen geen besef van de huidige datum hebben.

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Volgorde t.o.v. andere filters (laag = eerst).")
        add_date_context: bool = Field(
            default=True, description="Voeg de huidige datum/tijd toe als systeemcontext."
        )
        timezone: str = Field(default="Europe/Brussels", description="IANA-tijdzone voor de datum.")
        strip_whitespace: bool = Field(
            default=True, description="Verwijder overtollige witruimte uit de gebruikersprompt."
        )

    def __init__(self):
        self.valves = self.Valves()
        # Toon een aan/uit-knop bij het invoerveld zodat je dit per chat kunt schakelen.
        self.toggle = True

    def inlet(self, body: dict, __user__: dict = None) -> dict:
        messages = body.get("messages", [])

        # 1) Normaliseer de laatste gebruikersprompt (optioneel).
        if self.valves.strip_whitespace and messages:
            for m in reversed(messages):
                if m.get("role") == "user" and isinstance(m.get("content"), str):
                    m["content"] = "\n".join(
                        line.rstrip() for line in m["content"].strip().splitlines()
                    )
                    break

        # 2) Injecteer datum/tijd-context in (of vóór) de system message.
        if self.valves.add_date_context:
            try:
                now = datetime.now(ZoneInfo(self.valves.timezone))
                stamp = now.strftime(f"%A %d %B %Y, %H:%M ({self.valves.timezone})")
            except Exception:
                stamp = datetime.now().strftime("%A %d %B %Y, %H:%M")
            context = f"De huidige datum en tijd is: {stamp}."

            system_idx = next(
                (i for i, m in enumerate(messages) if m.get("role") == "system"), None
            )
            if system_idx is not None:
                messages[system_idx]["content"] = (
                    f"{context}\n\n{messages[system_idx].get('content', '')}".strip()
                )
            else:
                messages.insert(0, {"role": "system", "content": context})

        body["messages"] = messages
        return body

    def outlet(self, body: dict, __user__: dict = None) -> dict:
        # Geen nabewerking nodig; hook aanwezig als voorbeeld/uitbreidpunt.
        return body
