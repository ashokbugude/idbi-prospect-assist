"""The customer surface must never carry an internal tier or score.

A lead tier is a queue label for the bank. Showing a customer that they are a
"Window-shop Risk" would be meaningless to them and damaging to the bank, so the
separation is enforced here rather than left to reviewer discipline.
"""

from __future__ import annotations

import json

import pytest

from app.customer_view import WITHHELD_FIELDS, build_customer_view
from app.data_generator import generate_dataset
from app.scoring import LEAD_TIERS, score_customer_rules


def _payloads(n: int = 40):
    for raw in generate_dataset()[:n]:
        profile = score_customer_rules(raw)
        yield profile, build_customer_view(profile)


def test_no_withheld_key_reaches_the_customer():
    for profile, view in _payloads():
        for field in WITHHELD_FIELDS:
            assert field not in view, f"{field} leaked into the customer payload"


def test_no_tier_name_appears_anywhere_in_the_payload():
    for profile, view in _payloads():
        blob = json.dumps(view, ensure_ascii=False)
        for tier in LEAD_TIERS:
            assert tier not in blob, f"tier {tier!r} leaked into the customer payload"


def test_no_score_value_appears_anywhere_in_the_payload():
    for profile, view in _payloads():
        blob = json.dumps(view, ensure_ascii=False)
        score = profile.get("composite_lead_score")
        assert str(score) not in blob, f"composite score {score} leaked to the customer"


def test_the_customer_still_gets_something_useful():
    """Withholding the tier must not leave an empty page."""
    for _profile, view in _payloads(12):
        assert view["product"]
        assert view["indicative_emi"].startswith("₹")
        assert view["indicative_amount"].startswith("₹")
        assert len(view["messages"]) == 4
        assert view["data_inventory"]
        assert view["rights"]


@pytest.mark.parametrize("code", ["en", "hi", "mr", "ta"])
def test_every_language_renders_without_placeholders(code):
    _profile, view = next(_payloads(1))
    text = next(m["text"] for m in view["messages"] if m["code"] == code)
    assert "{" not in text and "}" not in text
    assert "₹" in text
    assert len(text) > 40


def test_rm_call_script_is_not_reused_for_the_customer():
    """RM briefs name the tier and the score — they are a different artefact."""
    from app.vernacular import build_vernacular_briefs

    for profile, view in _payloads(8):
        rm_lines = " ".join(
            " ".join(b.get("lines", [])) for b in build_vernacular_briefs(profile)
        )
        for message in view["messages"]:
            assert message["text"] not in rm_lines
