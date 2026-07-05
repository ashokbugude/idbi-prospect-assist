"""Synthetic 30-day transaction timeline for behavioral explainability."""

from __future__ import annotations

import random
from datetime import date, timedelta

TXN_CATEGORIES = (
    "salary_credit",
    "rent",
    "utilities",
    "groceries",
    "commute",
    "luxury",
    "savings_transfer",
    "emi_debit",
    "upi_retail",
    "cash_withdrawal",
)


def build_transaction_timeline(customer: dict, days: int = 30, seed: int | None = None) -> dict:
    """Build a tagged credit/debit timeline from customer behavioral profile."""
    rng = random.Random(seed if seed is not None else hash(customer.get("customer_id", "")) % 2**32)
    income = int(customer.get("monthly_income", 40000))
    need = float(customer.get("need_spend_ratio", 0.5))
    luxury = float(customer.get("luxury_spend_ratio", 0.15))
    savings = float(customer.get("savings_transfer_ratio", 0.08))
    day1_ratio = float(customer.get("salary_day_spend_ratio", 0.5))
    city = customer.get("city", "Mumbai")

    start = date.today().replace(day=1) - timedelta(days=days)
    entries: list[dict] = []

    salary_day = rng.randint(1, 3)
    entries.append({
        "date": (start + timedelta(days=salary_day)).isoformat(),
        "type": "credit",
        "category": "salary_credit",
        "label": "Salary / business credit",
        "amount": income,
        "location": city,
        "tag": "income",
    })

    if customer.get("pays_rent"):
        entries.append({
            "date": (start + timedelta(days=salary_day + 1)).isoformat(),
            "type": "debit",
            "category": "rent",
            "label": "Rent NEFT",
            "amount": int(income * 0.22),
            "location": city,
            "tag": "need",
        })

    daily_need = int(income * need / days)
    daily_luxury = int(income * luxury / days)
    luxury_burst = int(income * luxury * day1_ratio) if day1_ratio > 0.6 else 0

    for d in range(days):
        txn_date = start + timedelta(days=d)
        if d == salary_day and luxury_burst:
            entries.append({
                "date": txn_date.isoformat(),
                "type": "debit",
                "category": "luxury",
                "label": "Discretionary spend burst (day-1 pattern)",
                "amount": luxury_burst,
                "location": city,
                "tag": "luxury",
            })
        elif rng.random() < 0.55:
            cat = rng.choice(["groceries", "utilities", "commute", "upi_retail"])
            entries.append({
                "date": txn_date.isoformat(),
                "type": "debit",
                "category": cat,
                "label": cat.replace("_", " ").title(),
                "amount": daily_need + rng.randint(0, 400),
                "location": city,
                "tag": "need" if cat != "upi_retail" or rng.random() < 0.7 else "want",
            })
        if rng.random() < luxury * 2:
            entries.append({
                "date": txn_date.isoformat(),
                "type": "debit",
                "category": "luxury",
                "label": "Dining / electronics / lifestyle",
                "amount": daily_luxury + rng.randint(200, 2500),
                "location": city,
                "tag": "luxury",
            })

    if savings > 0.05:
        entries.append({
            "date": (start + timedelta(days=10)).isoformat(),
            "type": "debit",
            "category": "savings_transfer",
            "label": "SIP / savings transfer",
            "amount": int(income * savings),
            "location": city,
            "tag": "savings",
        })

    if customer.get("has_auto_emi") or customer.get("has_consumer_loan"):
        entries.append({
            "date": (start + timedelta(days=5)).isoformat(),
            "type": "debit",
            "category": "emi_debit",
            "label": "Existing loan EMI",
            "amount": int(income * float(customer.get("debt_to_income_ratio", 0.3)) * 0.4),
            "location": city,
            "tag": "obligation",
        })

    entries.sort(key=lambda e: e["date"])
    credits = sum(e["amount"] for e in entries if e["type"] == "credit")
    debits = sum(e["amount"] for e in entries if e["type"] == "debit")
    by_tag = {}
    for e in entries:
        if e["type"] == "debit":
            by_tag[e["tag"]] = by_tag.get(e["tag"], 0) + e["amount"]

    return {
        "days": days,
        "transaction_count": len(entries),
        "total_credits": credits,
        "total_debits": debits,
        "spend_by_tag": by_tag,
        "entries": entries[-40:],  # cap for UI
    }
