"""What the customer is allowed to see.

The RM surface and the customer surface are deliberately different. A lead tier
is an internal prioritisation construct: telling a customer they are a
"Window-shop Risk" would be both meaningless and harmful, and no part of this
payload may carry one. `WITHHELD_FIELDS` names what is excluded on purpose, and
tests/test_customer_view.py fails if any of it reaches the template.
"""

from __future__ import annotations

from app.fairness import DATA_INVENTORY
from app.next_best_action import PRODUCT_TENOR_MONTHS, indicative_ticket_inr

# Internal-only fields. Never serialise these into the customer payload.
WITHHELD_FIELDS = (
    "lead_tier",
    "lead_tier_css",
    "lead_priority",
    "composite_lead_score",
    "top_score",
    "all_scores",
    "purchase_intent",
    "behavioral_discipline",
    "repayment_capacity",
    "delinquency_risk",
    "recommended_action",
    "rm_workflow",
    "rm_call_eligible",
    "segment",
)

WITHHELD_EXPLAINED = [
    ("Your lead tier", "An internal queue label. It is not a credit decision and is never shown to you."),
    ("Your behavioural score", "Used to order the bank's call list, not to assess your application."),
    ("The relationship manager's script", "Internal coaching notes for the colleague who calls you."),
]

# One short customer-facing line per language. Deliberately not reused from the
# RM briefs: those name the tier and the score, which must not reach a customer.
_MESSAGES = {
    "en": ("Based on how your IDBI account has been used, you may be eligible for a "
           "{product} with an indicative EMI of around {emi} a month. "
           "This is an indication, not an offer or an approval."),
    "hi": ("आपके IDBI खाते के उपयोग के आधार पर, आप लगभग {emi} प्रति माह की अनुमानित EMI वाले "
           "{product} के लिए पात्र हो सकते हैं। यह केवल एक संकेत है — न प्रस्ताव, न स्वीकृति।"),
    "mr": ("तुमच्या IDBI खात्याच्या वापरावर आधारित, तुम्ही दरमहा अंदाजे {emi} EMI असलेल्या "
           "{product} साठी पात्र असू शकता. ही केवळ सूचना आहे — ऑफर किंवा मंजुरी नाही."),
    "ta": ("உங்கள் IDBI கணக்கு பயன்பாட்டின் அடிப்படையில், மாதம் சுமார் {emi} தோராயமான EMI உடன் "
           "{product} பெற நீங்கள் தகுதியுடையவராக இருக்கலாம். இது ஒரு குறிப்பு மட்டுமே — "
           "சலுகையோ ஒப்புதலோ அல்ல."),
}

_LANGS = [
    {"code": "en", "label": "English", "native": "English"},
    {"code": "hi", "label": "Hindi", "native": "हिन्दी"},
    {"code": "mr", "label": "Marathi", "native": "मराठी"},
    {"code": "ta", "label": "Tamil", "native": "தமிழ்"},
]

REVIEW_STATUS = "pending native-speaker review"


def _inr(value: int | float | None) -> str:
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        return "₹0"
    return f"₹{amount:,}"


def build_customer_view(profile: dict) -> dict:
    """Customer-safe payload. Nothing in WITHHELD_FIELDS may appear in here."""
    product = profile.get("top_product_label") or "loan"
    emi = int(profile.get("affordable_emi_estimate") or 0)
    tenor = PRODUCT_TENOR_MONTHS.get(profile.get("top_product", ""), 48)

    messages = [
        {
            "code": lang["code"],
            "label": lang["label"],
            "native": lang["native"],
            "text": _MESSAGES[lang["code"]].format(product=product, emi=_inr(emi)),
        }
        for lang in _LANGS
    ]

    return {
        "customer_id": profile.get("customer_id"),
        "name": profile.get("name", "Customer"),
        "city": profile.get("city", ""),
        "relationship_years": profile.get("relationship_years"),
        "product": product,
        "indicative_emi": _inr(emi),
        "indicative_amount": _inr(indicative_ticket_inr(profile)),
        "indicative_tenor_months": tenor,
        "messages": messages,
        "review_status": REVIEW_STATUS,
        "data_inventory": DATA_INVENTORY,
        "withheld": WITHHELD_EXPLAINED,
        "rights": [
            "You can see every category of data used, and why it was used.",
            "Account Aggregator consent is explicit, purpose-limited and revocable at any time.",
            "No automated decision is made about you — a person reviews every application.",
            "Nothing here is an offer. An application is assessed on its own merits.",
        ],
    }
