"""
title: Utilities
author: webui
author_url: https://github.com/open-webui
version: 0.1.0
license: MIT
description: Veilige rekenmachine, tijdzone-bewuste datum/tijd en eenheden-conversie.
requirements:
"""

# Open WebUI "Tool". Elke publieke methode van de class `Tools` met type-hints en
# een duidelijke docstring wordt als functie aan het model aangeboden (Native /
# Agentic function calling). Geen externe dependencies: alles uit de stdlib.

import ast
import operator
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

# --- Veilige expressie-evaluator (geen eval()) -----------------------------------
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Alleen getallen zijn toegestaan.")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Niet-toegestane expressie.")


class Tools:
    class Valves(BaseModel):
        default_timezone: str = Field(
            default="Europe/Brussels",
            description="Standaard tijdzone als er geen wordt opgegeven (IANA-naam).",
        )

    def __init__(self):
        self.valves = self.Valves()

    def calculator(self, expression: str) -> str:
        """
        Reken een wiskundige expressie veilig uit (geen variabelen of functies).
        Ondersteunt + - * / // % ** en haakjes. Gebruik dit voor elke rekenvraag.

        :param expression: De wiskundige expressie, bv. "17.3/100 * 4230" of "(2+3)**2".
        :return: Het resultaat als tekst, of een foutmelding.
        """
        try:
            tree = ast.parse(expression, mode="eval")
            result = _safe_eval(tree.body)
            return f"{expression} = {result}"
        except ZeroDivisionError:
            return "Fout: deling door nul."
        except Exception as e:
            return f"Fout bij het berekenen van '{expression}': {e}"

    def current_datetime(self, timezone: str = "") -> str:
        """
        Geef de huidige datum en tijd in een opgegeven tijdzone.
        Gebruik dit voor elke vraag over 'hoe laat is het' of de datum van vandaag.

        :param timezone: IANA-tijdzone, bv. "Asia/Tokyo" of "Europe/Brussels".
                         Laat leeg voor de standaard tijdzone.
        :return: Datum en tijd als leesbare tekst, of een foutmelding.
        """
        tz_name = timezone.strip() or self.valves.default_timezone
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            return (
                f"Onbekende tijdzone '{tz_name}'. Gebruik een IANA-naam zoals "
                f"'Europe/Brussels' of 'Asia/Tokyo'."
            )
        now = datetime.now(tz)
        return now.strftime(f"%A %d %B %Y, %H:%M:%S ({tz_name}, UTC%z)")

    def convert_units(self, value: float, from_unit: str, to_unit: str) -> str:
        """
        Converteer een waarde tussen veelvoorkomende eenheden (lengte, gewicht,
        temperatuur). Gebruik dit voor eenheden-omrekeningen.

        :param value: De numerieke waarde om te converteren.
        :param from_unit: Bron-eenheid: km, m, cm, mi, ft, in, kg, g, lb, oz, c, f, k.
        :param to_unit: Doel-eenheid (zelfde lijst).
        :return: Het geconverteerde resultaat als tekst, of een foutmelding.
        """
        f, t = from_unit.strip().lower(), to_unit.strip().lower()

        # Temperatuur apart (geen lineaire factor naar een basis-eenheid).
        temps = {"c", "f", "k"}
        if f in temps or t in temps:
            if f not in temps or t not in temps:
                return "Fout: meng geen temperatuur met andere eenheden."
            celsius = {"c": value, "f": (value - 32) / 1.8, "k": value - 273.15}[f]
            out = {"c": celsius, "f": celsius * 1.8 + 32, "k": celsius + 273.15}[t]
            return f"{value} {from_unit} = {round(out, 4)} {to_unit}"

        # Lengte (basis: meter) en gewicht (basis: gram).
        to_base = {
            "km": 1000.0, "m": 1.0, "cm": 0.01, "mi": 1609.344, "ft": 0.3048, "in": 0.0254,
            "kg": 1000.0, "g": 1.0, "lb": 453.59237, "oz": 28.349523125,
        }
        length = {"km", "m", "cm", "mi", "ft", "in"}
        weight = {"kg", "g", "lb", "oz"}
        if f not in to_base or t not in to_base:
            return f"Fout: onbekende eenheid. Ondersteund: {', '.join(sorted(to_base))}, c, f, k."
        if (f in length) != (t in length) or (f in weight) != (t in weight):
            return "Fout: kan lengte en gewicht niet door elkaar converteren."
        out = value * to_base[f] / to_base[t]
        return f"{value} {from_unit} = {round(out, 6)} {to_unit}"
