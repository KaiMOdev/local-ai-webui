"""
Offline unit-tests voor de OneDrive-connector: alleen de pure tekst-extractie
(_extract_text). Netwerk-/auth-paden worden hier niet getest.
"""

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "extensions" / "tools" / "onedrive.py"


def _load():
    spec = importlib.util.spec_from_file_location("owui_onedrive", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Tools


@pytest.fixture
def extract():
    return _load()._extract_text


def test_extract_plain_text(extract):
    assert extract("notes.txt", b"hallo wereld", 6000) == "hallo wereld"


def test_extract_json(extract):
    assert "key" in extract("data.json", b'{"key": 1}', 6000)


def test_extract_unsupported_binary(extract):
    out = extract("image.png", b"\x89PNG\r\n", 6000)
    assert "niet als tekst ondersteund" in out


def test_extract_truncates(extract):
    out = extract("big.txt", b"x" * 10000, 100)
    assert "afgekapt" in out
    assert len(out) < 200


def test_extract_empty(extract):
    assert "Leeg" in extract("empty.txt", b"", 6000)
