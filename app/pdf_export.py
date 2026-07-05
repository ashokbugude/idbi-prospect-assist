"""Underwriter packet PDF export."""

from __future__ import annotations

import io
import re

from fpdf import FPDF

_PAGE_W = 190


def _pdf_safe(text: str) -> str:
    return re.sub(r"[^\x00-\xff]", "-", str(text))


class UnderwriterPDF(FPDF):
    def header(self):
        self.set_fill_color(0, 131, 108)
        self.rect(0, 0, 210, 18, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "IDBI Prospect Assist AI - Underwriter Packet", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

    def section(self, title: str):
        self.set_text_color(0, 77, 64)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 46, 40)


def build_underwriter_pdf(profile: dict, raw: dict) -> bytes:
    pdf = UnderwriterPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.cell(0, 6, _pdf_safe(f"Customer: {profile.get('name')} ({profile.get('customer_id')})"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _pdf_safe(f"Tier: {profile.get('lead_tier')}  |  Composite: {profile.get('composite_lead_score')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _pdf_safe(f"Recommended: {profile.get('recommended_action', '')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.section("Income Inference")
    inc = profile.get("income_analysis") or {}
    pdf.cell(0, 5, f"Stated: INR {inc.get('stated_monthly_income', raw.get('monthly_income', 0)):,}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Inferred: INR {inc.get('inferred_monthly_income', 0):,}  (confidence {inc.get('income_confidence', 0):.0%})", new_x="LMARGIN", new_y="NEXT")
    if profile.get("holistic_monthly_income"):
        pdf.cell(0, 5, f"Holistic (multi-bank): INR {profile['holistic_monthly_income']:,}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.section("Delinquency Risk")
    dr = profile.get("delinquency_risk") or {}
    pdf.cell(0, 5, f"Band: {dr.get('risk_band', 'N/A')}  |  Score: {dr.get('score', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    for r in (dr.get("reasons") or [])[:3]:
        pdf.multi_cell(_PAGE_W, 5, _pdf_safe(f"- {r}"))

    pdf.section("Bureau")
    bu = profile.get("bureau_analysis") or {}
    pdf.cell(0, 5, f"Score: {bu.get('bureau_score', 'N/A')}  |  Band: {bu.get('credit_band', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(_PAGE_W, 5, _pdf_safe(bu.get("underwriting_hint", "")))

    pdf.section("Dimension Scores")
    for dim in ("repayment_capacity", "purchase_intent", "behavioral_discipline"):
        d = profile.get(dim) or {}
        pdf.cell(0, 5, f"{d.get('name', dim)}: {d.get('score', 0)}", new_x="LMARGIN", new_y="NEXT")
        for r in (d.get("reasons") or [])[:2]:
            pdf.multi_cell(_PAGE_W, 5, _pdf_safe(f"  - {r}"))

    pdf.section("Product Match")
    for p in (profile.get("all_scores") or [])[:3]:
        pdf.multi_cell(_PAGE_W, 5, _pdf_safe(f"{p.get('label')}: {p.get('score')} - {', '.join(p.get('reasons', [])[:1])}"))

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        _PAGE_W,
        4,
        "DPDP: Customer data used with consent. AI assists; underwriter makes final credit decision. "
        "POC synthetic data - replace with IDBI sandbox post-shortlist.",
    )

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
