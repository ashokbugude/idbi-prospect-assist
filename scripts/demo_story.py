"""The 3-minute demo: one story, used by recording, narration, and the one-shot.

Times are when the spoken line starts. The recorder navigates a beat earlier so
the page is already on screen when the voice comes in.
"""

from __future__ import annotations

from dataclasses import dataclass

FINAL_SECONDS = 178.5  # comfortably inside a 3:00 limit


@dataclass(frozen=True)
class Scene:
    at: float
    title: str
    screen: str
    line: str
    prep: float = 2.2  # seconds before `at` to start navigation


SCENES: tuple[Scene, ...] = (
    Scene(
        0.0, "hook", "Dashboard — KPI row",
        "IDBI converts one percent of its liability leads. Not because the customers "
        "are wrong. Because the branch cannot see which ones are real.",
        prep=0.0,
    ),
    Scene(
        14.0, "tiers", "Dashboard — queue",
        "Two hundred existing liability customers. Scored on capacity, intent, and "
        "discipline. Sixteen quality leads. Fifty-nine window shoppers the relationship "
        "manager should not call today. That last number is an afternoon, given back.",
        prep=0.0,
    ),
    Scene(
        32.0, "lead", "Customer — Why this tier",
        "Open any lead. The score explains itself, in business language. Salary credited "
        "on the first. Spend weighted to needs, not luxury. An underwriter can read this, "
        "and disagree. That is the point.",
        prep=2.6,
    ),
    Scene(
        52.0, "actions", "Actions — Next Best Action",
        "A score only matters when it becomes a Tuesday. Every recommendation is costed "
        "in rupees per R M minute, packed into a real branch day. Window shoppers are "
        "excluded from outbound. Structurally.",
        prep=2.3,
    ),
    Scene(
        70.0, "uplift", "Customer — uplift, what-if, vernacular",
        "Eleven levers. Each one a real re-score, not a chart. Move them while the "
        "customer is on the phone, and watch the tier. The call script is already in "
        "Hindi, Marathi, or Tamil.",
        prep=2.5,
    ),
    Scene(
        90.0, "aa", "Multi-bank — Account Aggregator",
        "Repayment capacity hides where the salary does not. One Account Aggregator "
        "consent pulls other-bank inflows. This lead changes tier on evidence the bank "
        "could not see a moment ago.",
        prep=2.3,
    ),
    Scene(
        108.0, "governance", "Governance — fairness, model risk, data quality",
        "Then the test a bank actually cares about. A live fair-lending audit. "
        "Four-fifths rule, every page load. The ratio is zero point four, flagged for "
        "review. We publish the failure rather than hide it.",
        prep=2.3,
    ),
    Scene(
        126.0, "outcomes", "Outcomes — calibration",
        "And the system finds out whether it was right. Every disposition is checked "
        "against the rate we assumed. At a hundred and fifty labelled outcomes, it retrains.",
        prep=2.2,
    ),
    Scene(
        138.0, "model", "Model — ML credibility",
        "Rules, plus a hybrid model. A safety cap of eight points. It never demotes a "
        "quality lead.",
        prep=2.2,
    ),
    Scene(
        148.0, "architecture", "Architecture — data flow",
        "The pipeline: enrichment, rules, XGBoost, the dashboard. On the page.",
        prep=2.6,
    ),
    Scene(
        158.0, "differentiators", "Differentiators",
        "Forty-three capabilities, each a link to the running build. Not a slide. A system.",
        prep=2.0,
    ),
    Scene(
        167.0, "impact", "Impact — Track 02 proof",
        "Twenty-five percent against one. Quality forty-one point three. "
        "Prospect Assist AI. Looking beyond the obvious.",
        prep=2.2,
    ),
)

WARM_PATHS = (
    "/",
    "/actions",
    "/outcomes",
    "/multi-bank",
    "/impact",
    "/governance",
    "/governance?tab=model-risk",
    "/governance?tab=data-quality",
    "/ml",
    "/architecture",
    "/differentiators",
    "/glossary",
    "/customer/IDBI-L10010",
)


def cues() -> list[tuple[float, str]]:
    return [(s.at, s.line) for s in SCENES]
