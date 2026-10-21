import json
from pathlib import Path

import pytest

from designazione.domain import RoundKey
from designazione.fip import parse_page

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def html():
    return (FIXTURES / "fip_a_round1.html").read_text(encoding="utf-8")


@pytest.fixture
def key():
    return RoundKey("85582", 1, 1)


@pytest.fixture
def page(html, key):
    return parse_page(html, key)


@pytest.fixture
def api_results():
    return json.loads((FIXTURES / "fip_api_a_round1.json").read_text())


@pytest.fixture
def api_ranking():
    return json.loads((FIXTURES / "fip_api_ranking_a.json").read_text())
