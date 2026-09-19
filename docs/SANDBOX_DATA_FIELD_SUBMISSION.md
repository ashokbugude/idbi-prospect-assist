# IDBI Innovate 2026 — Sandbox Data Field Submission (Srishti GenAI)

**Team:** Srishti GenAI · **Track:** Prospect Assist AI · **Leader:** Ashok Bugude  
**Email:** ashokbugude@gmail.com · **Live POC:** https://idbi-prospect-assist.onrender.com

The Google Form accepts **one API field per submission**. Submit this form **once per row** below (copy each column into the matching form field).

---

## APIs we need (3 sandbox endpoints)

| API | Method | Purpose |
|-----|--------|---------|
| `/sandbox/v1/customers/{customer_id}/transactions` | GET | Repayment capacity, income inference, need/want/luxury |
| `/sandbox/v1/customers/{customer_id}/bureau` | GET | Bureau cross-check, delinquency signals |
| `/sandbox/v1/customers/{customer_id}/digital` | GET | Purchase intent, window-shopping filter |

**Request parameter (all APIs):**

| API Field Name | Field Type | Max Length | Mandatory/Optional | Sample Values | Field Description |
|----------------|------------|------------|-------------------|---------------|-------------------|
| customer_id | String | 20 | Mandatory | IDBI-L10010 | Unique IDBI liability customer identifier |
| consent_reference | String | 50 | Mandatory | CONS_AA_20260819_001 | DPDP/AA consent audit reference for data pull |
| observation_days | Integer | 3 | Optional | 30, 90 | Lookback window for transactions/digital (default 30) |

---

## Response — Customer profile (shared header)

| API Field Name | Field Type | Max Length | Mandatory/Optional | Sample Values | Field Description |
|----------------|------------|------------|-------------------|---------------|-------------------|
| customer_id | String | 20 | Mandatory | IDBI-L10010 | Customer identifier echoed in response |
| name | String | 100 | Mandatory | Vikram Singh | Customer display name (masked acceptable) |
| city | String | 50 | Mandatory | Mumbai | Primary city for geo consistency checks |
| segment | String | 30 | Mandatory | Retail Liability | CASA / liability segment |
| employment_type | String | 20 | Mandatory | salaried | salaried, self_employed, or gig |
| business_type | String | 30 | Optional | services | Self-employed industry margin category |
| monthly_income | Integer | 10 | Mandatory | 85000 | Stated monthly income (INR) |
| relationship_years | Integer | 2 | Mandatory | 6 | Years of IDBI relationship |
| age | Integer | 3 | Mandatory | 38 | Customer age |
| response_status | String | 20 | Mandatory | SUCCESS | API processing result |

---

## Response — Transactions API

| API Field Name | Field Type | Max Length | Mandatory/Optional | Sample Values | Field Description |
|----------------|------------|------------|-------------------|---------------|-------------------|
| monthly_credit_inflow | Integer | 12 | Mandatory | 87200 | Total credit inflow in observation window (INR) |
| inferred_monthly_income | Integer | 12 | Optional | 91000 | Transaction-inferred monthly income (INR) |
| avg_monthly_balance | Integer | 12 | Mandatory | 42500 | Average monthly balance |
| need_spend_ratio | Decimal | 5,2 | Mandatory | 0.44 | Share of spend on essentials (rent, utilities, groceries) |
| luxury_spend_ratio | Decimal | 5,2 | Mandatory | 0.12 | Share of discretionary/luxury spend |
| savings_transfer_ratio | Decimal | 5,2 | Mandatory | 0.18 | Share transferred to savings/investments |
| salary_day_spend_ratio | Decimal | 5,2 | Mandatory | 0.28 | Spend intensity in first 3 days after salary credit |
| debt_to_income_ratio | Decimal | 5,2 | Mandatory | 0.32 | Existing EMI obligations / income |
| estimated_monthly_disposable | Integer | 12 | Mandatory | 18500 | Estimated post-obligation disposable cashflow (INR) |
| pays_rent | Boolean | 1 | Mandatory | true | Recurring rent debit detected |
| has_existing_home_loan | Boolean | 1 | Mandatory | false | Existing home loan EMI on account |
| has_mortgage | Boolean | 1 | Optional | false | Mortgage product flag |
| has_auto_emi | Boolean | 1 | Mandatory | true | Auto loan EMI detected |
| has_consumer_loan | Boolean | 1 | Mandatory | false | Consumer durable/personal loan EMI |
| monthly_commute_spend | Integer | 8 | Optional | 3200 | Average monthly commute/mobility spend (INR) |
| upi_retail_transactions | Integer | 4 | Mandatory | 24 | UPI retail transaction count in window |
| geo_transaction_consistency | Decimal | 4,2 | Mandatory | 0.94 | Share of txns in declared home city (0–1) |
| has_other_bank_accounts | Boolean | 1 | Mandatory | true | Multi-bank footprint indicator |
| multi_bank_income_share | Decimal | 5,2 | Optional | 0.22 | Estimated income share outside IDBI (0–1) |
| txn_date | Date | 10 | Mandatory | 2026-08-15 | Transaction date (YYYY-MM-DD) |
| txn_type | String | 10 | Mandatory | credit | credit or debit |
| txn_category | String | 30 | Mandatory | salary_credit | salary_credit, rent, groceries, luxury, emi_debit, upi_retail, savings_transfer |
| txn_amount | Integer | 12 | Mandatory | 85000 | Transaction amount (INR) |
| txn_location | String | 50 | Optional | Mumbai | City/merchant location |
| txn_tag | String | 20 | Mandatory | income | income, need, want, luxury, savings, emi |

---

## Response — Bureau API

| API Field Name | Field Type | Max Length | Mandatory/Optional | Sample Values | Field Description |
|----------------|------------|------------|-------------------|---------------|-------------------|
| credit_score_band | String | 1 | Mandatory | B | Bureau band A/B/C/D |
| bureau_normalized_score | Integer | 3 | Mandatory | 72 | Normalized bureau score 0–100 for underwriting |
| bureau_enquiries_90d | Integer | 2 | Mandatory | 2 | Credit enquiries in last 90 days |
| active_credit_accounts | Integer | 2 | Mandatory | 3 | Number of active credit accounts |
| credit_utilization_pct | Decimal | 5,2 | Mandatory | 0.38 | Revolving utilization ratio (0–1) |
| bureau_repayment_history_months | Integer | 3 | Mandatory | 48 | Months of clean repayment history |
| delinquency_flag_12m | Boolean | 1 | Mandatory | false | Any 30+ DPD in last 12 months |

---

## Response — Digital footprint API

| API Field Name | Field Type | Max Length | Mandatory/Optional | Sample Values | Field Description |
|----------------|------------|------------|-------------------|---------------|-------------------|
| loan_page_visits_30d | Integer | 3 | Mandatory | 8 | Loan product page visits in 30 days |
| loan_calculator_uses | Integer | 3 | Mandatory | 4 | EMI calculator usage count |
| avg_session_minutes | Decimal | 5,1 | Mandatory | 6.2 | Average session duration on loan journeys |
| application_started | Boolean | 1 | Mandatory | true | Customer started loan application |
| window_shopping_flag | Boolean | 1 | Mandatory | false | High browse + low commitment pattern |
| last_digital_event_at | DateTime | 19 | Optional | 2026-08-18T14:22:00 | Timestamp of latest digital event |

---

## Response — Scoring output (optional, for validation)

| API Field Name | Field Type | Max Length | Mandatory/Optional | Sample Values | Field Description |
|----------------|------------|------------|-------------------|---------------|-------------------|
| composite_lead_score | Integer | 3 | Optional | 78 | 0–100 composite lead score |
| lead_tier | String | 25 | Optional | Quality Lead | Quality Lead, Serious, Interested, Window-shop Risk |
| recommended_action | String | 150 | Optional | Priority RM callback within 24h | RM workflow recommendation |
| affordable_emi_estimate | Integer | 10 | Optional | 12400 | Affordable EMI from repayment capacity (INR) |

---

## Mentor session — 3 questions

1. **Sandbox integration priority:** For Track 02, should we prioritize transaction-inferred income, bureau fields, or digital clickstream first when wiring the sandbox — and what is the minimum viable field set IDBI expects in the refinement demo?

2. **RM pilot design:** For a 4-week A/B pilot (Quality + Serious vs control), what cohort size and success KPIs (conversion ≥32%, RM hours −40%) would IDBI consider credible for moving from POC to production?

3. **Governance & AA:** What consent, masking, and audit requirements apply when using sandbox transaction + multi-bank (AA) data in the scoring pipeline, and how should we demonstrate human-in-loop (no auto credit decision) to compliance reviewers?
