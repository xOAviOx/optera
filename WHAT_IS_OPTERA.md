# What is Optera? (a plain-English guide)

> Written for someone with **zero finance background**. No jargon without an explanation.
> If you remember one line: **Optera is a "co-pilot" that helps Indian options traders *see and understand the risk* in their trades — it explains, it never advises.**

---

## 1. The 10-second version

Imagine you're driving a car. Optera is **not** the driver, and it's **not** a GPS telling you "turn left here."

Optera is the **dashboard** — the speedometer, the fuel gauge, the "engine hot!" warning light. It shows you *what's happening* and *what could go wrong*, clearly, so **you** can decide what to do. It never grabs the steering wheel.

In finance terms: Optera connects to your trading account, **reads** your current trades (it can only look, never touch), does a lot of math to measure how risky they are, and then an AI explains that risk to you in simple language — even a mix of Hindi + English ("Hinglish").

**It will never tell you to buy or sell anything.** That's a hard rule baked into the app in three separate places. (More on why later.)

---

## 2. First, the tiny bit of finance you need

You only need to understand a few words. Here they are in the simplest form.

### Stocks vs. Options
- A **stock** (or "share") is a tiny slice of a company. Buy a share of a company, you own a tiny piece of it.
- An **option** is *not* the thing itself — it's a **contract about** the thing. Specifically, it's the **right (but not the duty)** to buy or sell something at a fixed price before a deadline. You pay a small fee for that right.

Think of a **movie ticket**: it gives you the *right* to watch a movie on Friday. You don't have to go. But the ticket has a price, and its value can change (a sold-out show → your ticket is worth more; a flop → worthless). Options work like that.

### The two kinds of options
- **Call option** = the right to **buy** at a fixed price. People buy calls when they think the price will **go up**.
- **Put option** = the right to **sell** at a fixed price. People buy puts when they think the price will **go down**.

### A few more words
- **Strike price** = the fixed price written in the contract.
- **Expiry** = the deadline date when the contract ends.
- **Premium** = the fee you pay to buy the option (or collect, if you *sell* one).
- **F&O** = "**F**utures & **O**ptions" — the category of this kind of trading in India. Optera focuses on the **O**.
- **NIFTY / BANK NIFTY** = famous Indian market *indexes* (a basket that represents "the market" or "the banking sector"). Tons of people trade options on these.
- **Position** = any trade you're *currently holding*. "Your positions" = everything you're currently in.
- **Retail trader** = a regular individual trading their own money (not a big bank). **That's Optera's user.**
- **Broker** = the app/company you actually trade through (Optera defaults to **Upstox**). Optera plugs into it **read-only**.

That's genuinely most of it. Now the interesting part.

---

## 3. The problem Optera solves

Options are powerful but **sneaky-risky**, for two reasons:

1. **They react to more than just price.** A stock is simple — it goes up, you gain; it goes down, you lose. An option's value also changes with **time** (it "melts" as the deadline nears) and with **how nervous the market is** (volatility). So you can be *right about the direction* and *still lose money*. Beginners get blindsided by this constantly.

2. **People combine several options at once.** Traders often hold 4–6 different option contracts together (these combos have names like "iron condor", "straddle"). The combined risk is *not obvious* by looking at them one by one. You need math to see the full picture.

Most retail traders have **no clear view of their real risk**. They see a list of trades and a profit/loss number, but not *"how much could I actually lose if the market drops 3% tomorrow?"* or *"how fast is time eating my position?"*

**Optera's whole job is to make that risk visible and understandable.**

---

## 4. What Optera actually does (feature by feature)

Each of these is a real page/screen in the app.

### 🔐 Sign in & onboarding (`/login`, `/onboarding`)
You create an account, agree to some **risk disclosures** (honest warnings that trading is risky and this is education-only), and connect your broker — **or** just use **Demo Mode** with fake data to explore safely.

### 📋 Positions (`/positions`)
A clean table of the option trades you currently hold, pulled **live and read-only** from your broker, with the profit/loss on each. This is the "here's what you're holding right now" screen.

### 📊 Risk (`/risk`) — the heart of the app
This is where the math shows up as something you can actually read:
- **Portfolio Greeks** — a few numbers that summarize your total risk (explained in the next section).
- **Payoff diagram** — a *picture* of your profit/loss at different prices. It turns a confusing 5-option combo into one simple chart: where you make money, where you lose, your **maximum possible loss**, and your **break-even** points.
- **Scenario / "what-if"** — "If NIFTY drops 2% tomorrow, you'd be down about ₹X." You can stress-test your trades against imagined market moves.
- **Probability of Profit (POP)** — an estimated **% chance** your trade ends up making money (like a weather forecast: "70% chance of profit" — odds, not a promise).

### ⛓️ Option Chain (`/chain`)
The **option chain** is the full "menu" of available option contracts for something like NIFTY — every strike and expiry with its price and volatility. Optera also shows **IV Rank**: is the market's nervousness **high or low right now** compared to its own recent history? (Useful context, not a recommendation.)

### 🤖 AI Co-pilot (`/copilot`)
A chat box where you can ask things like:
- *"What's my risk right now?"*
- *"What happens if the market falls 3%?"*
- *"Explain my Greeks like I'm five."*

The AI pulls **your real numbers** using built-in tools (it can fetch your Greeks, summarize your payoff, and run what-if scenarios) and explains them in plain Hinglish. A safety filter (see §6) makes sure it **explains** and never **advises**.

### 🎮 Simulator / Paper Trading (`/simulator`)
Practice with **fake money** on a simulated market. Place pretend trades, watch them play out, learn how options behave — **with zero real risk**. Perfect for a beginner. (This is the safest place for *you* to start.)

### 📓 Journal (`/journal`)
A logbook where you can save hypothetical strategies and keep notes on your trades — to learn from what you did.

### 🔔 Alerts & Monitoring
You can set **rules** ("warn me if my risk crosses a limit") and Optera sends **alerts** phrased in plain language, so you're not caught off guard.

---

## 5. The scary-sounding words ("the Greeks"), explained with everyday analogies

Traders measure an option's risk with four Greek-letter numbers. They sound intimidating; they're actually simple sensitivities — *"if X changes, how much does my position change?"*

| Name | What it measures | Everyday analogy |
|---|---|---|
| **Delta** | How much you gain/lose when the price moves a little | **Speed** — how fast your money moves as the market moves |
| **Gamma** | How fast your *Delta* itself changes | **Acceleration** — how quickly that speed ramps up (high gamma = things change *fast*) |
| **Theta** | How much value you lose **each day**, just from time passing | A **melting ice cube** — options quietly lose value as the deadline nears |
| **Vega** | How much you gain/lose when **volatility** (market nervousness) changes | Sensitivity to the market's **mood swings** |

And two more terms you'll see:
- **Implied Volatility (IV)** = the market's guess of how wildly a price will swing, baked into the option's price. High IV = expensive options (big moves expected). Think of it as the market's **"insurance premium"** or nervousness level.
- **Margin** = a security deposit your broker locks up for certain trades (especially when you *sell* options). Optera shows how much of it your positions are using.

Optera computes all of these **across your whole portfolio at once** and puts them in plain language. That's the magic: you don't need to *do* the math — you just need to *read the dashboard*.

---

## 6. The golden rule: what Optera will NOT do (and why)

This is the most important part, and it's deliberate.

**Optera is education & analytics ONLY. It never gives buy / sell / hold advice, price predictions, or "you should…" suggestions.**

Why so strict?
- Telling people what to trade is **regulated financial advice** — legally serious, and easy to get wrong in a way that hurts people's money.
- Optera's value is helping you **understand and decide for yourself**, not gambling on your behalf.

How it's enforced (three layers, treated like a security wall):
1. **The AI's instructions** tell it to explain, never advise.
2. A **server-side "advice filter"** scans the AI's replies and blocks anything that sounds like a recommendation (e.g. phrases like "I recommend…"), so even if the AI slips, it gets caught.
3. **Disclaimers in the UI** on every output surface remind you it's education only.

Two more hard limits:
- **Read-only broker access.** Optera can *see* your trades but **cannot place, change, or cancel** any order. It literally has no button to trade.
- **Strategy building is hypothetical/paper only** — you can explore "what if I did this?" without any real order ever happening.

**In short: Optera is a teacher and a dashboard, not a broker and not a tipster.**

---

## 7. How it's built (a simple peek under the hood)

You don't need this to *use* the app, but since it's your project, here's the shape of it:

- **Two parts working together:**
  - **The website** (`apps/web`) — everything you see and click. Dark theme, works on your phone.
  - **The engine** (`apps/engine`) — the "brain" that does the heavy math and talks to the AI.
- **The "quant core"** is the math library inside the engine. It prices options and computes Greeks, payoffs, scenarios, and probabilities. Crucially, it's **tested against textbook reference values** (40+ tests) so the numbers are trustworthy — no hand-wavy math.
- **AI is used only to *explain*,** never to decide: a chat model (Gemini) for the co-pilot, and a fast model (Groq) to phrase alerts. The provider is swappable via config.
- **Your data is private.** Each user only ever sees their own data (enforced at the database level in Supabase). Your broker access tokens are **encrypted** and never leave the server — they're never sent to your browser.
- **Built to be free to run (₹0/month)** and **India-first**: rupees (₹), lakh/crore number formatting, and Indian market hours (9:15 AM–3:30 PM IST).

---

## 8. A quick story: using Optera end to end

1. You **sign in** and connect Upstox (read-only) — or flip on **Demo Mode**.
2. The **Positions** page shows the option trades you're holding.
3. You open **Risk** and finally *see it*: a payoff chart, your max loss, and a note that says time decay (Theta) is costing you about ₹1,200/day.
4. You're nervous about tomorrow, so you ask the **Co-pilot**: *"What if NIFTY falls 3%?"* It runs the numbers on *your* positions and explains, in Hinglish, that you'd be down roughly ₹X and why.
5. It **never** says "so you should sell" — it just makes the risk crystal clear. **You** decide.
6. Want to practice an idea first? You try it in the **Simulator** with fake money, risk-free.

That's Optera: **see your risk clearly, understand it, learn — and stay in control.**

---

## 9. Mini-glossary (all in one place)

| Term | Plain meaning |
|---|---|
| **Option** | A contract giving the *right* (not obligation) to buy/sell at a fixed price before a deadline |
| **Call / Put** | Right to **buy** / right to **sell** |
| **Strike** | The fixed price in the contract |
| **Expiry** | The contract's deadline date |
| **Premium** | The fee to buy (or collect, if selling) an option |
| **F&O** | Futures & Options — the Indian trading category Optera serves |
| **Position** | A trade you currently hold |
| **Broker** | The service you trade through (Upstox); Optera connects **read-only** |
| **Option chain** | The full "menu" of available options for a symbol |
| **Delta / Gamma / Theta / Vega** | Speed / acceleration / time-melt / mood-sensitivity of your position |
| **IV (Implied Volatility)** | Market's expected swinginess; the "nervousness premium" |
| **Payoff diagram** | A chart of your profit/loss at different prices |
| **Scenario / what-if** | Stress-testing your trades against imagined market moves |
| **POP** | Probability of Profit — estimated % odds a trade makes money |
| **Margin** | Security deposit the broker locks up for certain trades |

---

*Remember: Optera is a dashboard and a teacher, not a driver and not a tipster. It shows you the risk in plain words — the decisions are always yours.*
