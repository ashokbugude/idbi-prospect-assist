# Demo video — 3:00 recording + narration

Track 02 · Prospect Assist AI · IDBI Innovate 2026

One command builds the take — records the live app (no caption bar) and lays a
neural voice over it:

```
python scripts/make_demo_video.py
```

Target length **2:58.5**. The story, cue times and spoken lines live in
`scripts/demo_story.py` so the picture and the voice share one clock.

---

## Before you hit record

1. **Warm the site** — `make_demo_video.py` does this itself. If you record by
   hand, open every page once first (Render's free tier sleeps).
2. **Log in before the clock starts.** The script signs in, then trims the PIN.
3. Browser at **1920×1080**. The recorder sets this.
4. Do **not** burn captions into a take you will narrate. `--captions` exists
   only for a silent cut.

---

## The script

Times are when the line *starts*. The recorder navigates ~2 seconds earlier so
the page is already on screen when the voice comes in.

| Time | On screen | Say |
|---|---|---|
| **0:00** | Dashboard — KPI row | "IDBI converts one percent of its liability leads. Not because the customers are wrong. Because the branch cannot see which ones are real." |
| **0:14** | Dashboard — queue | "Two hundred existing liability customers. Scored on capacity, intent, and discipline. Sixteen quality leads. Fifty-nine window shoppers the relationship manager should not call today. That last number is an afternoon, given back." |
| **0:32** | Customer — Why this tier | "Open any lead. The score explains itself, in business language. Salary credited on the first. Spend weighted to needs, not luxury. An underwriter can read this, and disagree. That is the point." |
| **0:52** | Actions — Next Best Action | "A score only matters when it becomes a Tuesday. Every recommendation is costed in rupees per R M minute, packed into a real branch day. Window shoppers are excluded from outbound. Structurally." |
| **1:10** | Customer — uplift, what-if, vernacular | "Eleven levers. Each one a real re-score, not a chart. Move them while the customer is on the phone, and watch the tier. The call script is already in Hindi, Marathi, or Tamil." |
| **1:30** | Multi-bank — Account Aggregator | "Repayment capacity hides where the salary does not. One Account Aggregator consent pulls other-bank inflows. This lead changes tier on evidence the bank could not see a moment ago." |
| **1:48** | Governance — fairness, model risk, data quality | "Then the test a bank actually cares about. A live fair-lending audit. Four-fifths rule, every page load. The ratio is zero point four, flagged for review. We publish the failure rather than hide it." |
| **2:06** | Outcomes — calibration | "And the system finds out whether it was right. Every disposition is checked against the rate we assumed. At a hundred and fifty labelled outcomes, it retrains." |
| **2:18** | Model — ML credibility | "Rules, plus a hybrid model. A safety cap of eight points. It never demotes a quality lead." |
| **2:28** | Architecture — data flow | "The pipeline: enrichment, rules, XGBoost, the dashboard. On the page." |
| **2:38** | Differentiators | "Forty-three capabilities, each a link to the running build. Not a slide. A system." |
| **2:47** | Impact — Track 02 proof | "Twenty-five percent against one. Quality forty-one point three. Prospect Assist AI. Looking beyond the obvious." |

**Ends 2:58.5.**

Pages visited: Dashboard, lead explainability, Actions, Uplift / what-if / vernacular, Multi-bank, Governance (all three tabs), Outcomes, Model, Architecture, Differentiators, Impact.

---

## Pieces

| Command | What it does |
|---|---|
| `python scripts/make_demo_video.py` | Record + neural voice + verify |
| `python scripts/record_demo.py` | Silent picture only |
| `python scripts/add_narration.py --tts` | Neural voice onto the silent take |
| `python scripts/add_narration.py --audio my.wav` | Your own voice instead |

Neural TTS needs `pip install edge-tts`. Without it the Windows built-in voice
is used (`--sapi`).

---

## After it is recorded

Upload it (YouTube unlisted is safest for judges — no login wall), then
regenerate the deck so slide 13 carries the link:

```
set DEMO_VIDEO_URL=https://your-link-here
python scripts\update_submission_ppt.py
```
