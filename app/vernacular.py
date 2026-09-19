"""
Vernacular RM call briefs — Hindi, Marathi and Tamil.

An IDBI branch RM in Pune or Coimbatore does not open the call in English. The
brief is the first sentence of a real conversation, so it is generated in the
language the RM will actually speak.

Deliberately template-driven rather than model-generated: a bank cannot put an
unreviewed machine translation in front of a customer, and the demo must not
depend on a live API key. Every string here is fixed, reviewable, and version
controlled — the numbers are injected, the wording is not invented per call.

NOTE FOR REVIEW: these strings were authored for a working demo. Have a native
speaker from the relevant circle sign off each language before any pilot — the
`reviewed_by` field is deliberately empty until that happens.
"""

from __future__ import annotations

LANGUAGES: list[dict[str, str]] = [
    {"code": "en", "label": "English", "native": "English", "script": "Latin"},
    {"code": "hi", "label": "Hindi", "native": "हिन्दी", "script": "Devanagari"},
    {"code": "mr", "label": "Marathi", "native": "मराठी", "script": "Devanagari"},
    {"code": "ta", "label": "Tamil", "native": "தமிழ்", "script": "Tamil"},
]

TIER_TERMS = {
    "hi": {
        "Quality Lead": "उच्च गुणवत्ता वाली",
        "Serious": "गंभीर",
        "Interested": "इच्छुक",
        "Window-shop Risk": "केवल जानकारी लेने वाली",
    },
    "mr": {
        "Quality Lead": "उच्च दर्जाची",
        "Serious": "गंभीर",
        "Interested": "इच्छुक",
        "Window-shop Risk": "फक्त चौकशी करणारी",
    },
    "ta": {
        "Quality Lead": "உயர் தரமான",
        "Serious": "தீவிரமான",
        "Interested": "ஆர்வமுள்ள",
        "Window-shop Risk": "வெறும் விசாரணை",
    },
}

PRODUCT_TERMS = {
    "hi": {
        "Home Loan": "गृह ऋण",
        "Mortgage Loan": "संपत्ति पर ऋण",
        "Auto Loan": "वाहन ऋण",
        "Personal Loan": "व्यक्तिगत ऋण",
        "Consumer Durable Loan": "उपभोक्ता वस्तु ऋण",
    },
    "mr": {
        "Home Loan": "गृहकर्ज",
        "Mortgage Loan": "मालमत्तेवरील कर्ज",
        "Auto Loan": "वाहन कर्ज",
        "Personal Loan": "वैयक्तिक कर्ज",
        "Consumer Durable Loan": "ग्राहक वस्तू कर्ज",
    },
    "ta": {
        "Home Loan": "வீட்டுக் கடன்",
        "Mortgage Loan": "சொத்து அடமானக் கடன்",
        "Auto Loan": "வாகனக் கடன்",
        "Personal Loan": "தனிநபர் கடன்",
        "Consumer Durable Loan": "நுகர்வோர் பொருள் கடன்",
    },
}

DISCLAIMERS = {
    "hi": "यह AI-सहायित सुझाव है। अंतिम निर्णय RM और अंडरराइटर का होगा।",
    "mr": "हा AI-सहाय्यित सल्ला आहे. अंतिम निर्णय RM आणि अंडररायटर घेतील.",
    "ta": "இது AI உதவியுடன் உருவாக்கப்பட்ட பரிந்துரை. இறுதி முடிவு RM மற்றும் அண்டர்רைட்டரிடம்.",
}


def _inr(value: int | float | None) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def _lines_hi(ctx: dict) -> list[str]:
    if ctx["suppress"]:
        return [
            f"{ctx['name']} को बिक्री कॉल न करें — यह ग्राहक अभी केवल जानकारी ले रहा है "
            f"(स्कोर {ctx['score']}/100)।",
            "इसके बजाय वित्तीय जागरूकता से जुड़ी सामग्री भेजें और 30 दिन बाद दोबारा मूल्यांकन करें।",
        ]
    if ctx["nurture"]:
        return [
            f"{ctx['name']} अभी {ctx['tier']} श्रेणी में हैं (स्कोर {ctx['score']}/100) — "
            "तुरंत कॉल करने के बजाय पहले डिजिटल माध्यम से संपर्क करें।",
            f"{ctx['product']} का EMI कैलकुलेटर लिंक भेजें; मासिक EMI क्षमता लगभग ₹{ctx['emi']} है।",
        ]
    return [
        f"{ctx['name']} को कॉल करें — यह {ctx['tier']} श्रेणी की लीड है (स्कोर {ctx['score']}/100)।",
        f"मासिक आय ₹{ctx['income']}, अनुमानित EMI क्षमता ₹{ctx['emi']} प्रति माह।",
        f"{ctx['product']} का प्रस्ताव दें और IDBI के साथ {ctx['years']} वर्ष के संबंध का उल्लेख करें।",
    ]


def _lines_mr(ctx: dict) -> list[str]:
    if ctx["suppress"]:
        return [
            f"{ctx['name']} यांना विक्री कॉल करू नका — हा ग्राहक सध्या फक्त चौकशी करत आहे "
            f"(स्कोअर {ctx['score']}/100).",
            "त्याऐवजी आर्थिक साक्षरतेची माहिती पाठवा आणि ३० दिवसांनी पुन्हा मूल्यांकन करा.",
        ]
    if ctx["nurture"]:
        return [
            f"{ctx['name']} सध्या {ctx['tier']} गटात आहेत (स्कोअर {ctx['score']}/100) — "
            "लगेच कॉल करण्याऐवजी प्रथम डिजिटल माध्यमातून संपर्क साधा.",
            f"{ctx['product']} चा EMI कॅल्क्युलेटर दुवा पाठवा; अंदाजे EMI क्षमता ₹{ctx['emi']} आहे.",
        ]
    return [
        f"{ctx['name']} यांना कॉल करा — ही {ctx['tier']} लीड आहे (स्कोअर {ctx['score']}/100).",
        f"मासिक उत्पन्न ₹{ctx['income']}, अंदाजे EMI क्षमता ₹{ctx['emi']} प्रति महिना.",
        f"{ctx['product']} बद्दल बोला आणि IDBI सोबतच्या {ctx['years']} वर्षांच्या नात्याचा उल्लेख करा.",
    ]


def _lines_ta(ctx: dict) -> list[str]:
    if ctx["suppress"]:
        return [
            f"{ctx['name']} அவர்களுக்கு விற்பனை அழைப்பு வேண்டாம் — இவர் தற்போது தகவல் மட்டுமே "
            f"பார்க்கிறார் (மதிப்பெண் {ctx['score']}/100).",
            "அதற்குப் பதிலாக நிதி விழிப்புணர்வு தகவல்களை அனுப்பி, 30 நாட்களில் மீண்டும் மதிப்பிடவும்.",
        ]
    if ctx["nurture"]:
        return [
            f"{ctx['name']} தற்போது {ctx['tier']} பிரிவில் உள்ளார் (மதிப்பெண் {ctx['score']}/100) — "
            "உடனே அழைப்பதற்குப் பதிலாக முதலில் டிஜிட்டல் வழியில் தொடர்பு கொள்ளவும்.",
            f"{ctx['product']} EMI கால்குலேட்டர் இணைப்பை அனுப்பவும்; மதிப்பிடப்பட்ட EMI திறன் ₹{ctx['emi']}.",
        ]
    return [
        f"{ctx['name']} அவர்களை அழைக்கவும் — இது {ctx['tier']} வகை வாய்ப்பு "
        f"(மதிப்பெண் {ctx['score']}/100).",
        f"மாதாந்திர வருமானம் ₹{ctx['income']}, மதிப்பிடப்பட்ட EMI திறன் மாதம் ₹{ctx['emi']}.",
        f"{ctx['product']} பற்றி பேசுங்கள்; IDBI உடனான {ctx['years']} ஆண்டு உறவைக் குறிப்பிடுங்கள்.",
    ]


_BUILDERS = {"hi": _lines_hi, "mr": _lines_mr, "ta": _lines_ta}


def _context(profile: dict, language: str) -> dict:
    tier = profile.get("lead_tier", "Interested")
    product_en = profile.get("top_product_label", "Personal Loan")
    return {
        "name": profile.get("name", "Customer"),
        "score": profile.get("composite_lead_score", 0),
        "tier": TIER_TERMS.get(language, {}).get(tier, tier),
        "product": PRODUCT_TERMS.get(language, {}).get(product_en, product_en),
        "income": _inr(profile.get("monthly_income")),
        "emi": _inr(profile.get("affordable_emi_estimate")),
        "years": profile.get("relationship_years") or 1,
        "suppress": tier == "Window-shop Risk",
        "nurture": tier == "Interested",
    }


def build_vernacular_briefs(profile: dict) -> list[dict]:
    """One brief per supported language, ready for the RM to read aloud."""
    briefs = []
    for lang in LANGUAGES:
        code = lang["code"]
        if code == "en":
            continue
        ctx = _context(profile, code)
        briefs.append({
            **lang,
            "lines": _BUILDERS[code](ctx),
            "disclaimer": DISCLAIMERS[code],
            "reviewed_by": "",  # left empty until a native speaker signs off
            "review_status": "pending native-speaker review",
        })
    return briefs


def language_options() -> list[dict[str, str]]:
    return LANGUAGES
