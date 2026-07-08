"""GenAI-style RM call brief — template + optional LLM enhancement."""

from __future__ import annotations

import os
import re


def _bold_to_html(text: str) -> str:
    """Convert **label** markers to <strong> for HTML display."""
    parts = re.split(r"\*\*(.+?)\*\*", text)
    out: list[str] = []
    for i, part in enumerate(parts):
        if not part:
            continue
        if i % 2 == 1:
            out.append(f"<strong>{part}</strong>")
        else:
            out.append(part)
    return f"<p>{''.join(out)}</p>"


def _template_brief(profile: dict) -> str:
    name = profile.get("name", "Customer")
    tier = profile.get("lead_tier", "Interested")
    product = profile.get("top_product_label", "Personal Loan")
    composite = profile.get("composite_lead_score", 0)
    repayment = profile["repayment_capacity"]["score"]
    intent = profile["purchase_intent"]["score"]
    discipline = profile["behavioral_discipline"]["score"]
    action = profile.get("recommended_action", "Review profile")

    income_note = ""
    inc = profile.get("income_analysis") or {}
    if inc.get("inferred_monthly_income") and inc.get("stated_monthly_income"):
        if inc["inferred_monthly_income"] > inc["stated_monthly_income"] * 1.1:
            income_note = (
                f" Transaction data suggests higher repayment capacity "
                f"(inferred ₹{inc['inferred_monthly_income']:,} vs stated ₹{inc['stated_monthly_income']:,})."
            )

    avoid = []
    if profile.get("purchase_intent", {}).get("details", {}).get("window_shopping_flag"):
        avoid.append("do not hard-sell without confirming funding timeline")
    delinq = profile.get("delinquency_risk", {})
    if delinq.get("risk_band") in ("Medium", "High"):
        avoid.append("avoid aggressive EMI stretch — discuss conservative ticket size")
    if profile.get("bureau_analysis", {}).get("normalized_score", 100) < 50:
        avoid.append("bureau weakness — lead with secured/product-fit narrative")

    avoid_text = f" Avoid: {'; '.join(avoid)}." if avoid else ""

    if tier == "Window-shop Risk":
        return (
            f"**Why deprioritize {name}:** {tier} (score {composite}) — browsing-heavy pattern with weak "
            f"{product} commitment. Repayment {repayment}/100, intent {intent}/100, "
            f"discipline {discipline}/100.{income_note} "
            f"**Do not place an RM sales call.** **RM action:** {action}.{avoid_text}"
        )

    if tier == "Interested":
        opener = f"**Why nurture {name}:**"
        pitch = (
            f"**Nurture:** Share {product} EMI calculator and light-touch digital follow-up — "
            f"confirm funding timeline before RM escalation."
        )
    else:
        opener = f"**Why call {name}:**"
        pitch = (
            f"**Pitch:** Lead with {product}, reference their IDBI relationship and affordable EMI capacity."
        )

    return (
        f"{opener} {tier} (score {composite}) with strong {product} fit — "
        f"repayment {repayment}/100, intent {intent}/100, discipline {discipline}/100.{income_note} "
        f"{pitch} **RM action:** {action}.{avoid_text}"
    )


def _llm_brief(profile: dict) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        tier = profile.get("lead_tier", "Interested")
        if tier == "Window-shop Risk":
            brief_goal = (
                "Write a 3-sentence deprioritization brief for an IDBI loan officer. "
                "Explain why NOT to call, what automated nurture to use instead, and what to avoid. "
                "Do not recommend an RM sales call."
            )
        elif tier == "Interested":
            brief_goal = (
                "Write a 3-sentence nurture brief for an IDBI loan officer. "
                "Cover: why nurture digitally, what to share, when to escalate to a call."
            )
        else:
            brief_goal = (
                "Write a 3-sentence RM call brief for an IDBI loan officer. "
                "Cover: why call, what to pitch, what to avoid."
            )
        prompt = (
            f"{brief_goal} Professional tone.\n"
            f"Profile JSON keys: name={profile.get('name')}, tier={tier}, "
            f"product={profile.get('top_product_label')}, composite={profile.get('composite_lead_score')}, "
            f"action={profile.get('recommended_action')}"
        )
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


def generate_rm_brief(profile: dict) -> dict:
    llm_text = _llm_brief(profile)
    brief = llm_text or _template_brief(profile)
    brief_plain = re.sub(r"\*\*(.+?)\*\*", r"\1", brief)
    return {
        "brief": brief_plain,
        "brief_html": _bold_to_html(brief),
        "source": "openai" if llm_text else "srishti_genai_template",
        "disclaimer": "AI-assisted brief — RM makes final outreach decision (human-in-loop).",
        "source_label": "Live LLM brief" if llm_text else "Template brief",
    }
