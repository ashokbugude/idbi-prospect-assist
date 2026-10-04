# Demo day playbook — IDBI Innovate 2026 final

**10 minutes live + 5 minutes Q&A · top-5 shortlist · Monday**

You are not a novice. You have 13 years of engineering and six building production AI.
What you lack is about twenty banking words, and those are in section 4 below. Learn
those and you can hold any conversation in that room.

---

## 1. The one idea the whole demo rests on

Do not open by describing your product. Open by reframing their problem.

They think the problem is *finding good leads*. It isn't. The problem is *spending
relationship-manager time on bad ones*. Ninety-nine people get the same call as the
one person who was actually going to borrow.

Every screen you show is evidence for that one reframe. If a judge remembers one
sentence from you, it should be: **"We do not make more calls. We make fewer, better
ones, and we can prove which ones not to make."**

---

## 2. Before you walk in

- [ ] **Warm the site 10 minutes early.** Render's free tier sleeps and cold start takes
      up to 50 seconds. Open every page you plan to show — `/`, a customer, `/actions`,
      `/customer-view`, `/multi-bank`, `/governance`, `/outcomes`, `/impact` — so all of
      them are warm.
- [ ] **Log in before you share your screen.** Never type a PIN on camera.
- [ ] **Three fallbacks, in this order.** Live Render site → `localhost:8000` running in a
      second window → the recorded video. If Render stalls for more than five seconds,
      say "I'll switch to the local instance, same build" and move. Do not wait. Do not
      apologise twice.
- [ ] Browser at 100% zoom, bookmarks bar hidden, one window, notifications off.
- [ ] Have `/impact` open in the last tab so your closing numbers are one click away.
- [ ] Phone on silent, in another room.

---

## 3. The ten minutes

Times are when each section *starts*. The cut markers tell you what to drop if you are
running late — decide in the moment, don't rush everything.

### 0:00 — The reframe (45 seconds, no screen share yet)

> "IDBI converts about one percent of its liability-customer leads. I assumed for a
> while that meant the leads were bad. They aren't. The problem is that a relationship
> manager cannot tell a serious borrower from someone running an EMI calculator out of
> curiosity — so the ninety-nine get the same call as the one.
>
> Everything I'm going to show you in the next nine minutes exists to fix that one
> thing. It's live, it's running now, and the APIs are open so your team can check every
> number I quote."

Then share your screen on the dashboard.

### 0:45 — Dashboard: the number that matters is 59

Point at the tier row: 200 customers, 16 Quality, 30 Serious, 95 Interested, **59
Window-shop Risk**.

> "Two hundred existing CASA customers, scored on three things: can they repay, do they
> actually intend to buy, and are they disciplined with money. Four tiers come out.
>
> Most lead tools would have me point at the sixteen Quality Leads. I want to point at
> the fifty-nine. That's thirty percent of this book that an RM should not call today —
> thirty percent of a working day handed back."

Hit the **Before / After** toggle. "Left is spray-and-pray. Right is the prioritised
queue. Same leads, same RMs." Then move — do not scroll the table.

### 1:50 — One lead: the score explains itself

Click a Quality Lead. Scroll to **Why this tier?**

> "Every score explains itself. Not feature weights — the actual reasons, in language an
> underwriter can argue with. Salary lands on the first. Rent and EMI outflows are
> visible. The spend mix leans to needs rather than luxury.
>
> And nothing here decides anything. The machine-learning layer can move this score by at
> most eight points and can never demote a Quality Lead. The underwriter still decides."

### 2:50 — Customer View: the same lead from the other side (50 seconds)

Click **Customer** in the nav. This is a short beat — do not linger.

> "That's what the bank sees. This is what the customer sees, and they are deliberately
> different."

Scroll straight to **What we never show you**.

> "The customer never sees their tier or their score — those are internal queue labels.
> Telling someone they're a 'Window-shop Risk' would be meaningless to them and damaging
> to you. They see an indicative eligibility, in their own language, and every data
> category we hold.
>
> And this isn't a promise in a document — a test fails the build if a tier or a score
> ever reaches this page."

Then move on immediately. One pivot, one proof point, done.

*Cut marker: if you are past 3:50 here, skip Actions and go straight to Multi-bank.*

### 3:40 — Actions: a score that became a decision

Click **Actions**.

> "A score is useless until it becomes an action. Every recommendation is costed in
> rupees per RM minute, and the day is packed into real branch capacity — SLA
> commitments first. And notice what's missing: no outbound call to anyone in the
> window-shop tier. That isn't a setting someone can forget to switch on. The system
> structurally cannot recommend cold-calling a lead it just flagged as low intent."

### 4:30 — Account Aggregator: the money you can't see

Go to **Multi-bank**. Grant consent for **IDBI-L10055**. Let it fetch.

> "Here's the case your RMs lose most often. This customer looks ordinary on IDBI data
> alone, because most of their money lands at another bank.
>
> One Account Aggregator consent — the RBI framework, so the customer never shares a
> password — and we re-score on holistic income. To be precise: in production that
> consent happens in the customer's own AA app. What I just clicked is a simulation of
> that step."

Point at the tier change.

> "Interested, to Serious. Not because we guessed better, but because the bank could now
> see income it genuinely could not see sixty seconds ago."

Your strongest visual. Pause after "sixty seconds ago."

### 5:40 — The part that decides whether you can deploy it

Go to **Governance**. This is where you win or lose the room. Slow down.

> "The three questions your model-risk function will ask: is it fair, will it be audited,
> and will it still be right in six months.
>
> First — fairness. This runs the four-fifths test on every page load, against the actual
> model inputs, not a report someone wrote once."

**Say the hard thing yourself, before anyone asks:**

> "And it's currently reporting zero point four. That's below the threshold. It's a
> finding, and I've published it in the product rather than hiding it, because a fairness
> number you only discover in month three is worth nothing. Here's the mitigation
> simulation showing what closes the gap."

Click **Model risk**.

> "Every decision writes an append-only record — engine version, model version, the
> reasons. Nothing is ever edited; a correction is a new entry. And the drift monitor
> ships with its alarm demonstrated firing, not just described."

Click **Data quality**.

> "We removed each upstream data source in turn. The scorer survives all five, and missing
> data is scored as unknown — never as good news. A customer with no debt data doesn't get
> credit for having no debt."

### 7:25 — It finds out whether it was right

Go to **Outcomes**.

> "Every disposition an RM logs is checked against the conversion rate we assumed for that
> tier. Assumptions become measurements, in public. At a hundred and fifty labelled
> outcomes it's ready to retrain on what actually happened rather than on my rules."

### 8:15 — The ask

Go to **Impact**.

> "The simulation: the prioritised queue converts at twenty-five percent against a one
> percent baseline, and the Quality segment at forty-one — against a Track 02 target of
> thirty-two.
>
> I want to be precise about what that is. It's a Monte Carlo backtest on synthetic data.
> It is not a measured result, and I'd rather tell you that than have you find it.
>
> So what I'd ask for is four weeks. One branch cluster, your real leads, the prioritised
> queue against a control group, measured on conversion. If it doesn't beat your baseline,
> you've lost four weeks of one RM's calling list. If it does, you have a scoring layer
> that already passes model-risk review."

Stop at **9:30**. Don't keep talking. Silence is fine.

### If you are given more than ten minutes

Don't stretch everything — add one thing, in this order of value:

1. **The Uplift Simulator** (60s, on the lead page): eleven levers, each re-scored through
   the production engine. Move a what-if slider and let them watch the tier change.
2. **Differentiators** (30s): scroll it, don't read it. "Forty-three, each linked to the
   page where you can verify it."

If the slot is strictly ten minutes, going over reads as poor judgement and costs you
more than the extra content gains. The Q&A is where finals are won.

## 4. The twenty words

The only real gap. Learn these and the room sounds familiar.

| Term | What it means | Where it touches your product |
|---|---|---|
| **CASA** | Current Account / Savings Account — everyday deposit accounts | Your 200 customers are all CASA holders |
| **Liability customer** | Someone whose money the bank *holds* (a depositor). The bank owes them | Your input |
| **Asset customer** | Someone who owes the bank — a borrower | Your output. **You turn liability customers into asset customers.** Know this cold |
| **Cross-sell** | Selling an existing customer another product | Exactly what this does |
| **RM** | Relationship Manager — the person who makes the call | Your whole product protects their time |
| **Conversion rate** | Share of leads that become actual loans | Your 1% → 25% story |
| **Ticket size** | The rupee value of a loan | Appears in your Next Best Action costing |
| **EMI** | Equated Monthly Instalment — the fixed monthly loan payment | Your affordability gates |
| **Repayment capacity** | Can they actually afford the EMI | One of your three dimensions |
| **DTI** | Debt-to-income: existing obligations ÷ income. Higher is riskier | A scoring input |
| **FOIR** | Fixed Obligation to Income Ratio — what Indian banks usually call DTI | **If someone says FOIR, they mean your DTI.** Don't blink |
| **Bureau score / CIBIL** | Credit score from a credit bureau | A scoring input |
| **Underwriting** | The process (and person) that approves or declines a loan | Your PDF packet feeds this; the underwriter decides, not you |
| **Delinquency** | Missing payments | Your 12-month stress signal |
| **NPA** | Non-Performing Asset — a loan 90+ days overdue. The thing banks fear | What good scoring prevents |
| **Account Aggregator (AA)** | RBI-licensed consent framework for sharing financial data between institutions, without sharing passwords | Your multi-bank flow |
| **FIP / FIU** | Financial Information Provider (gives data) / User (receives it). IDBI would be the FIU here | AA plumbing |
| **KYC** | Know Your Customer — identity verification | Not in scope; say so if asked |
| **TAT** | Turnaround time | Pilot KPI |
| **Fair lending** | Not disadvantaging protected groups in credit decisions | Your governance page |
| **Disparate impact / four-fifths rule** | If one group is approved at less than 80% the rate of the best group, that's a flag | Your 0.40 finding |
| **Model risk management** | The bank's process for validating a model before it's allowed near customers | Your entire governance pack exists for this |
| **Model drift / PSI** | Whether live data has shifted away from what the model was trained on | Your drift monitor |
| **DPDP Act 2023** | India's data protection law | Your data inventory page |
| **STP** | Straight-through processing — fully automated, no human | **You are deliberately not STP.** Say that proudly |
| **Propensity model** | A model predicting likelihood to buy | They may call your product this. Fine |

---

## 5. The five minutes of Q&A

Short answers. Two to four sentences. Stop talking when you're done.

**"Is this real IDBI data?"**
> No. Two hundred synthetic customers, seed-controlled so it's reproducible. I built a
> typed field contract and a sandbox API stub so that when you give me access, the real
> feed drops in without the scoring logic changing.

**"Your fairness ratio is 0.40. That's a fail."**
> It is, and I'd rather show it than hide it. It's flagged for review, and the page
> carries a mitigation simulation showing what closes the gap. On synthetic data the
> number itself isn't meaningful — what matters is that the test runs on every page load
> against live model inputs, so when it's your data, you find out immediately rather than
> in month three.

**"Did you build this, or did AI build it?"**
> I used AI tooling throughout — that's how I work, and it's on my CV. I own the
> architecture, the scoring design and the test suite. Eighty-nine tests, and the
> governance layer exists because I went looking for ways this could be wrong. Ask me
> anything in it.

**"How is this different from the propensity model we already have?"**
> Most propensity models tell you who to call. This also tells you who *not* to call, and
> measures what that saves. And it's built to pass model-risk review on day one — audit
> log, fairness test, drift monitor — rather than having that bolted on afterwards.

**"What does the customer see?"**
> Let me show you — it's a page. They never see their tier or their score; those are
> internal queue labels. They see an indicative eligibility in their own language, every
> data category we hold, the lawful basis, and that AA consent is revocable. A test fails
> the build if a tier or score ever reaches that page.

**"Could an RM show a customer the wrong screen?"**
> In the demo both sit behind one login so you can inspect the boundary. In production the
> customer side isn't a tab in the RM portal at all — it's a separate consented channel,
> the app or the AA consent screen, with its own authentication.

**"What data do you need from us?"**
> CASA balances, salary credits, transaction history, and bureau band if you have it.
> The architecture page lists the field contract. It degrades gracefully — I tested
> removing each source group in turn and the scorer survives all five.

**"Does it make the credit decision?"**
> No, and deliberately not. It prioritises who to talk to. The ML layer can move a score
> by at most eight points and can never demote a Quality Lead. The underwriter decides.

**"What if the RM ignores it?"**
> Then we find out. Every disposition is logged against what we assumed, so if RMs are
> overriding the queue the calibration page shows it. That's a signal about the model,
> not about the RM.

**"Can you explain a decision to a regulator, or to a customer who was declined?"**
> Nobody is declined by this — it's prioritisation, not adjudication. But yes: every
> decision has an audit record with the engine version, model version and the reasons,
> and it's queryable and exportable.

**"What would a pilot cost?"**
> The demo runs on free-tier hosting at zero. A four-week pilot on your sandbox is a few
> hundred dollars a month of cloud. The real cost is RM time, and the pilot is designed
> to measure whether that time comes back.

**"How long to integrate?"**
> The sandbox stub is already there with the typed contract. Realistically, weeks not
> months, and most of it is your side — access, approvals, security review.

**"What about customers with no digital footprint?"**
> That was a bug I found and fixed. Early on, a customer with no digital data fell out of
> the queue entirely, which structurally excluded branch-acquired customers. Now missing
> signals cap the tier at Serious rather than removing the lead — unverified is not the
> same as bad.

**"Why you, over the other four?"**
> Hard to answer about them. What I'd say about this one: it's live, the code is public,
> the APIs need no login, and it reports its own failures. You can check everything I've
> said tonight without me in the room.

### If you don't know

You will get a banking question you can't answer. The worst thing you can do is bluff
to a room of bankers. Use this, and mean it:

> "I don't know what IDBI's current practice is there. Here's what the system does today
> and the reasoning behind it — tell me if that's wrong for your context and it's a
> configuration change, not a rebuild."

That answer makes you look like a consultant. Bluffing makes you look like a vendor.

---

## 6. Things not to do

- **Don't demo the glossary or the differentiators catalogue.** They're proof for judges
  reading offline, not demo material. They eat time and show nothing moving.
- **Don't show code, file names or the terminal.** Ever.
- **Don't say "the AI decided".** Say what decided — the rule engine, the scorer, the
  thresholds.
- **Don't get defensive about synthetic data.** Raise it first, explain the contract,
  move on. Defensiveness reads as concealment.
- **Don't overclaim 41%.** Call it a simulated backtest every single time. If they catch
  you inflating one number, every other number you said is now suspect.
- **Don't run over.** At 10:00 stop, even mid-sentence. Going long reads as poor judgment
  and the Q&A is where you actually win.
- **Don't apologise for nerves, the free tier, or anything else.** One acknowledgement
  maximum if something breaks, then carry on.

---

## 7. Rehearse these three things only

If you only have an hour this weekend:

1. **The opening 45 seconds, word for word, out loud, five times.** If you land the
   reframe the rest is downhill.
2. **The Account Aggregator click path**, until the consent-to-re-score sequence is
   muscle memory. It's your best visual and the one most likely to be fumbled.
3. **Saying "zero point four is below the threshold" without flinching.** Practise until
   it sounds like confidence rather than confession — because it is.
