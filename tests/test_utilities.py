"""
Unit-tests voor de offline (netwerkloze) logica van de Utilities-tool.
We laden het bestand per pad, omdat de extensies losse bestanden zijn (geen package).
"""

import importlib.util
from pathlib import Path

import pytest

_UTIL_PATH = Path(__file__).resolve().parents[1] / "extensions" / "tools" / "utilities.py"


def _load_tools():
    spec = importlib.util.spec_from_file_location("owui_utilities", _UTIL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Tools()


@pytest.fixture
def tools():
    return _load_tools()


# --- calculator -----------------------------------------------------------------
def test_calculator_basic(tools):
    assert tools.calculator("2 + 3 * 4") == "2 + 3 * 4 = 14"


def test_calculator_percentage(tools):
    # 17,3% van 4230
    assert "731" in tools.calculator("0.173 * 4230")


def test_calculator_power_and_parens(tools):
    assert tools.calculator("(2 + 3) ** 2") == "(2 + 3) ** 2 = 25"


def test_calculator_division_by_zero(tools):
    assert "nul" in tools.calculator("1 / 0").lower()


def test_calculator_rejects_code_injection(tools):
    # Geen namen/aanroepen toegestaan -> foutmelding, geen uitvoering.
    result = tools.calculator("__import__('os').system('echo hacked')")
    assert "Fout" in result


def test_calculator_rejects_attribute_access(tools):
    assert "Fout" in tools.calculator("(1).__class__")


# --- convert_units --------------------------------------------------------------
def test_convert_length_km_to_m(tools):
    assert "1000" in tools.convert_units(1, "km", "m")


def test_convert_temperature_c_to_f(tools):
    assert "32.0" in tools.convert_units(0, "c", "f")


def test_convert_rejects_mixed_dimensions(tools):
    assert "Fout" in tools.convert_units(1, "kg", "m")


def test_convert_rejects_unknown_unit(tools):
    assert "Fout" in tools.convert_units(1, "parsec", "m")


# --- current_datetime -----------------------------------------------------------
def test_datetime_default_timezone(tools):
    out = tools.current_datetime()
    assert "Europe/Brussels" in out


def test_datetime_explicit_timezone(tools):
    out = tools.current_datetime("Asia/Tokyo")
    assert "Asia/Tokyo" in out


def test_datetime_unknown_timezone(tools):
    out = tools.current_datetime("Not/AZone")
    assert "Onbekende tijdzone" in out
