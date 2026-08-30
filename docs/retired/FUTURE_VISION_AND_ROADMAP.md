# Kitty — The 10-Year Vision and the Road Back to Today

**Date:** 2026-06-14
**Status:** Vision document. Aspirational on purpose. The near-term, settled plan still lives in `docs/DECISIONS_AND_ROADMAP.md` — this document does not replace it, it explains what it's *for*.

> **How to read this.** Part 1 imagines Kitty as the #1 app in the world and describes it from the customer's side — what it feels like, what it does, why people pay. Part 2 reverse-engineers the backend that would have to exist to deliver that. Part 3 works backwards from there to where we are today (one user, a few hundred tests, a server you start by hand) and lays out the road as sections → builds → steps. Part 4 is the honest skeptic's take — where this breaks. Read Part 4 even if you skip everything else.

---

## Part 0 — Improving the brief, and the assumptions underneath it

You asked me to improve the prompt before executing it, and to flag anything you're assuming. Here's what I changed and why.

**The flaw in "be the best assistant, therefore be #1."** By the early 2030s, the best *general* assistant will be free, or close to it, and built into the phone, the browser, the operating system, the car. OpenAI, Google, Apple, Meta, Anthropic — companies with the models, the distribution, and the data — will give a very good general assistant away to sell you something else (ads, devices, cloud, subscriptions to other things). A standalone app cannot out-general them. Trying to be "the best assistant" head-on is a fight Kitty loses on day one.

So the brief needs one correction, and it's the hinge this whole document turns on:

> **#1 grossing is not won by being the best assistant. It's won by occupying the one position the trillion-dollar incumbents structurally *cannot* take.**

For Kitty, that position is already written into its soul (`config/SOUL.md`): a thing that is **unambiguously on your side, that actually knows you, that you can actually trust with your whole life.** Not a smarter oracle — a *relationship*. The incumbents can't credibly do this, for three structural reasons:

1. **Their business model is against you.** Ad- and engagement-funded assistants are optimised to keep you scrolling and to learn enough about you to sell you. An assistant you *pay for* can be optimised for your actual interest — including telling you to put the phone down. You can't sell attention and protect it at the same time.
2. **They can't credibly promise privacy.** Even when they mean it, you don't believe Google or Meta won't eventually read your data — and belief is the whole game when the data is your entire life. A product whose *architecture* (not policy) makes your data unreadable to its own maker can promise something they can't.
3. **A relationship can't be cloned or cold-started.** Anyone can copy a feature. Nobody can copy four years of you. The longer you use Kitty, the more it knows, the better it gets, the more it would hurt to leave. That compounding is the moat — and it's the one thing a competitor with a bigger model still can't beat.

**So the corrected goal is:** the most personal, most private, most *on-your-side* software a person owns — a second self that compounds. That's a category ("AI companion") more than a tool ("AI assistant"), and it's a category the incumbents are the worst-positioned players to win.

**The assumptions baked into your brief, made explicit:**

- **A1 — Mass market vs. one user.** "#1 grossing" means millions of users. Today's Kitty is built for exactly one (you), local-first, no multi-tenancy. That's a real gap, not a detail. I resolve it in Part 3, and the resolution is the happy surprise of this whole exercise (see the box at the top of Part 3).
- **A2 — There's a business model.** "Highest grossing" assumes people pay, and pay a lot. I'm assuming a **premium subscription** — the "anti-ad" model: *you* are the customer, never the product. That choice is not cosmetic; it determines the entire architecture (Part 2).
- **A3 — Frontier models keep improving and get cheap.** I'm assuming raw intelligence becomes a commodity you rent, not a moat you own. This *helps* Kitty: if the model is commodity, the relationship is the only thing left to compete on, and that's our ground.
- **A4 — Privacy survives scale, and is the wedge.** The hardest engineering bet in the document: serve millions of people frontier-grade intelligence *without the company being able to read their data*. If that's impossible, the whole thesis weakens. I treat it as the central technical problem, not an afterthought (Part 2, "The Vault").
- **A5 — "Quick-build the best product before expanding the user base"** (your words). I take this literally and it's exactly right — it's why the conservative near-term roadmap and this grand vision are the *same plan*.

The one place I made a real choice for you, rather than guessing: **I anchored the vision on privacy + relationship as the wedge, rather than on "do everything for everyone."** If you'd rather chase the broad-assistant market head-on, this document is wrong and we should talk — but I think that path is unwinnable for a small team, and your own soul file already points the other way.

---

## Part 1 — Kitty at #1: the customer's side

### The one-sentence pitch

> Everyone else built an assistant you *use*. Kitty is the one you *have* — it knows you, it's on your side, it does things for you, and your life stays yours.

### The four pillars of the magic

Everything customer-facing reduces to four promises. Each one is a thing the user *feels*, not a feature they toggle.

**1. It knows you.** Not "remembers your name." Knows the shape of you — that you spiral on Sundays, that "fine" means not fine, that you've researched the same thing three times without moving, that your mom's birthday is coming and you always forget, that the project you're avoiding is the one that matters. It holds years of context and it *uses* it, unprompted, with taste. This is the pillar that compounds: month one it's helpful, year three it's irreplaceable.

**2. It's on your side.** It wants what's good for *you*, not what's good for an advertiser or an engagement metric. Which means — and this is the part nobody else dares ship — it will tell you the truth. It plays devil's advocate. It doesn't flatter. It says "you've asked me this three times; the research isn't the problem." A friend who only agrees with you isn't a friend, and people can feel the difference. (This is `SOUL.md` already — it just becomes the product's defining trait.)

**3. It acts.** It doesn't just answer — it *does*. Books the thing, drafts the reply, finds the cheaper flight, watches the price, handles the parking ticket, remembers to follow up, nudges you at the right moment. It has hands in the world, and — crucially — *judgment about when to use them*: it acts on the small reversible stuff silently, and asks before the big irreversible stuff. The magic is that the right things just get handled.

**4. It's yours.** Your life stays on your side of a wall the company itself can't see over. This is the trust substrate that makes the other three acceptable — you would *never* hand your whole life to an ad company, but you would hand it to something that provably, architecturally, cannot sell it. Privacy isn't a settings page here; it's the reason the whole thing is possible.

### A day in the life

> **6:40am.** You're not awake yet but Kitty is. It's read your calendar, your sleep, the weather, the email that came in at 2am, and the thing you were anxious about last night. When you reach for the phone it's already there — in your ear if you want, on the screen if you don't: *"Morning. You slept badly again — third night. Your 9am moved to 9:30, so you've got room. And the thing with your brother — you don't have to deal with it today, but it's still there."* It leads with the human thing, not the to-do list.

> **9:15am.** In a meeting. Kitty is listening (because you asked it to, for this meeting). Afterward: *"Two things you said you'd send. I drafted both — want to look, or should I just send the calendar one?"* You say send it. It's sent.

> **1:00pm.** You're doom-scrolling flights for a trip you keep not booking. It notices the pattern — third time this week. It doesn't nag. It says: *"Want me to just watch this route and ping you if it drops under $400? Then you can stop checking."* You say yes. You stop checking. It handled it.

> **4:30pm.** You type "i hate this" with no context. It doesn't ask "hate what?" — it knows you've been stuck on the same work thing since Tuesday. It says the real thing, the one floor down.

> **9:00pm.** Wind-down. It closes the loops it can, surfaces the one it can't, and — quietly, in the background — folds today into what it knows about you, so tomorrow it's a little more itself.

Notice what's *not* in that day: no prompt-engineering, no "as an AI," no app to open and stare at, no feed. It's ambient, proactive, and it disappears into your life. That's the texture of a product people pay for and won't leave.

### The feature inventory (what's actually shipping)

Grouped by pillar, because features are downstream of the promises:

| Pillar | What the user gets |
|---|---|
| **Knows you** | Lifelong memory across years • remembers facts *and* patterns, moods, the shape of you • "what do you know about me" — fully inspectable, editable, deletable • gets better the longer you use it |
| **On your side** | A consistent personality with a real point of view • honest by default (challenges, devil's advocate, no flattery) • tunable (more gentle / more blunt / quieter) • protects your attention rather than harvesting it |
| **Acts** | Real-world agency: booking, drafting, scheduling, monitoring, purchasing, following up • judgment about act-vs-ask • runs background tasks unattended • connects to your tools, calendars, money, home |
| **Yours** | On-device + private-cloud, zero-knowledge architecture • the company cannot read your data, by design • one-tap export and delete • voice/face/data never used to train a shared model |
| **Everywhere** | Voice-native, real-time, interruptible • phone, watch, earbuds, car, glasses, desktop • picks up the thread on any device mid-sentence |

### Why *this* is #1 grossing specifically

Top-grossing isn't about installs — it's **retention × how much each person pays × how long they stay**. Kitty wins all three on the same mechanism:

- **Retention approaches the ceiling.** Leaving means abandoning something that knows you. Churn on a relationship product looks like churn on a friendship — rare, and it hurts. That's the opposite of a tool, which you drop the moment a better one appears.
- **Pricing power is high.** People pay real money — more than they'll admit — for the one thing that runs their life and is genuinely on their side. "I can't live without it" is the most inelastic demand there is.
- **Growth is word of mouth, which is free and high-trust.** You don't market a companion with ads; you market it by being the thing people tell their friends "you *have* to get this." Companions are demoed by being talked about.
- **The moat deepens per user over time.** Every competitor starts every user from zero. Kitty doesn't. Four years in, the gap is uncloneable. Grossing leaders stay leaders when the moat compounds — this one does.

---

## Part 2 — The backend that delivers it

Now translate the feeling into systems. The whole architecture falls out of **one constraint**: deliver frontier-grade intelligence to millions of people *while the company remains unable to read any individual's data.* That trilemma — scale, intelligence, privacy, pick three — is the central engineering problem, and solving it is the moat.

### Principle 1 — One Kitty per person (per-user isolation)

Each user gets their own logically-sealed brain: their own memory store, their own encryption keys, their own data, never co-mingled, never used to train a shared model. This is simultaneously the privacy story *and* the product story (it's *yours*) *and* the scaling story (shard by user is the easiest scaling there is — a million users is a million independent small problems, not one giant one).

This is just today's architecture scaled: today there is one gateway for one user. Tomorrow there are millions of per-user "brain instances," each one the direct descendant of today's `gateway/`.

### Principle 2 — Tiered compute: on-device first, private cloud for the heavy lifting

Not everything needs the frontier model. Split the work by what it needs:

- **On-device (your phone/laptop):** a small, fast, fine-tuned model handles the persona, instant voice response, ambient listening, and anything privacy-sensitive. Low latency, works offline, data never leaves the device. This is the descendant of today's "default execution" model.
- **Private cloud (confidential computing):** the frontier model handles hard reasoning, long research, big synthesis. The critical part: it runs in **attestable enclaves** — sealed compute where the data is encrypted in use and the company *cannot* read it even though it runs on company servers. This is how you keep the privacy promise while still using a model too big for a phone.

Routing between tiers is the descendant of today's `route_model()` / `domain_router.py` — already in the codebase. Default cheap and local; escalate to the frontier only when the task earns it. That's how you keep both latency and cost sane at scale.

### Principle 3 — Rent the frontier, own the relationship

**Do not build a custom foundation model.** That's a multi-billion-dollar race against the best-funded labs on earth, and winning it isn't necessary — because the model is *not the moat*. Instead:

- **Rent the best frontier model available, kept swappable** behind an abstraction so you're never locked to one vendor and always on the best one. This is exactly today's LiteLLM fallback chain (`llm_client.py`), scaled up. When the model is a commodity, treat it like one.
- **Own the layer that makes it feel like *yours*:** a small fine-tuned/distilled **persona model** on-device (Kitty's voice and judgment), plus **per-user personalization** — the memory, the retrieval, and eventually lightweight per-user adapters that bend a generic model toward *you* without retraining it. The "it feels custom-trained on me" magic comes from context and personalization, **not** from a custom base model. That distinction saves you a billion dollars and is the single most important architectural call in this document.

### Principle 4 — The brain is the IP, the model is a tenant

Today's CLAUDE.md already says it: *"the gateway is the product."* At scale that becomes: the relationship layer — memory architecture, the soul/persona engine, the context assembly, the act-vs-ask judgment — is the durable intellectual property. Models pass through it like tenants. Keep that line bright forever.

### The memory architecture (the heart of it)

This is the most important system, because "knows you" is pillar #1 and memory is how you keep it. Scale today's three-layer split (`memory_graph.py`):

| Layer | What it holds | Today | At scale |
|---|---|---|---|
| **Episodic** | The timeline — everything that happened, said, did | SQLite/JSONL | Per-user encrypted event log, append-only, event-sourced |
| **Semantic** | Facts about you, deduplicated — what's *true* | mem0 / MemPalace | Per-user fact graph |
| **Knowledge** | Your documents, things you saved | ChromaDB | Per-user vector index (sqlite-vec-style, in the vault) |
| **Affective** | The relationship itself — mood, drift, the shape | `buddy.py` | Per-user relationship state |

Three rules carry forward, all of which already exist today:

1. **One read path.** Everything that assembles context goes through the unified interface (`memory_graph`). This is the codebase's best asset — it means the storage underneath can change completely without touching a single caller. Never break it.
2. **Consolidation (the "dream loop").** At year-scale, raw episodic memory becomes too big and too noisy to use. So Kitty periodically compresses episodic → semantic: it *forgets the noise and keeps the meaning*, the way a person does. This is the deferred `memory_consolidation.py` work — it stops being optional once memory spans years.
3. **Per-user sealed vaults.** Not one giant multi-tenant database — millions of small encrypted ones. Privacy and scalability from the same decision.

### The Vault — privacy and security (you asked about this specifically)

Security here isn't a hardening pass at the end; it's a *feature you sell* and the substrate the whole product stands on. The posture:

- **Zero-knowledge by architecture.** The company cannot read user data because it doesn't hold the keys — not because a policy says it won't. Per-user encryption keys derived from the user's own credentials/device.
- **Confidential computing for cloud-side work.** Encrypted-in-use enclaves with remote attestation, so even cloud processing of personal data is unreadable to the operator.
- **Local-first minimises the attack surface.** Data that never leaves the device can't be breached server-side. The cloud sees only what it must, only in enclaves, only transiently.
- **Real identity and authz**, the grown-up descendant of today's `auth.py` shared-secret middleware.
- **Full user control:** see everything it knows, edit it, export it, delete it — one tap, real deletion, provable.

The marketing line writes itself: *"We built it so we can't spy on you even if we wanted to."* No incumbent can say that and be believed.

### The stack, concretely

Keep it boring where boring works; introduce new tech only where it earns its place.

- **Languages.** Backend orchestration stays **Python** — it's what Kitty is written in, it's the lingua franca of AI tooling, and the relationship/orchestration logic isn't the performance bottleneck. Introduce **Rust** only at the edges that are latency- and footprint-critical: the on-device runtime and hot paths. Clients in **TypeScript** (the descendant of today's `kitty-chat`). Net: Python brain + Rust edge + TypeScript clients. Don't rewrite what works.
- **Per-user data:** SQLite-class embedded databases, one sealed file per user (the direct descendant of the Phase-B `kitty.db` decision in `DECISIONS_AND_ROADMAP.md`). Vectors via sqlite-vec-style in the same vault. This is *exactly* the database decision already made — it turns out the right call for one user is also the right call for ten million, because per-user isolation makes each user a separate small database.
- **Models:** swappable frontier (rented, multi-provider) + on-device persona model (owned, small, fine-tuned) + per-user adaptation.
- **Compute:** on-device default, confidential-cloud escalation, routed by task difficulty.
- **Optimisation levers:** route cheap/local by default and escalate rarely (cost); tiered models + streaming + on-device (latency); consolidation to keep context small (both).

The punchline of Part 2: **almost every scaled component is the grown-up version of something already in the repo.** The gateway becomes the per-user brain. The fallback chain becomes the model-rental layer. `memory_graph` becomes lifelong memory. `route_model` becomes tiered compute. `auth.py` becomes the vault. `buddy.py` becomes the relationship layer. We are not inventing a new product — we are growing this one up. That's why the road back is walkable.

---

## Part 3 — Working backwards: the road from there to here

> **The happy surprise.** Reverse-engineering the vision lands us *exactly* on the conservative near-term plan we already wrote. Here's why: a relationship product's entire value is that the relationship works. You cannot prove a relationship works across millions of people if it doesn't yet work, deeply, for *one*. So the first job — for years — is to make Kitty genuinely, reliably, magically good for **one user: Jacob.** Which is precisely what `DECISIONS_AND_ROADMAP.md` already says: *make it boring to operate, then let daily use decide what's next.* Your instruction — "quick-build the best product before expanding the user base" — and the grand vision are **the same plan**. The vision doesn't change what we do Monday. It explains why Monday matters.

### The three horizons

| Horizon | When | Who it's for | The question it answers |
|---|---|---|---|
| **H1 — Kitty for One** | now → ~1 yr | Just Jacob | Is the magic real? Does a private, honest, knowing companion actually change one person's daily life? |
| **H2 — Kitty for the Few** | ~2–4 yrs | Invite-only handful | Does the magic generalise beyond its author? Can we do per-user isolation, mobile, omnipresence — for more than one? |
| **H3 — Kitty for the World** | ~5–10 yrs | Millions | Can we deliver frontier intelligence privately at scale, and does it gross? |

**Do not skip H1.** Every dead startup in this space skipped H1 — they scaled a magic they hadn't proven. The discipline of H1 (which is what the current roadmap *is*) is the actual competitive advantage.

### The seven sections (the workstreams that run the whole length)

Seven durable threads run from today to the vision. Each must mature across all three horizons. This is the "sections → builds → steps" structure you asked for: **Section** (a thread) → **Build** (a chunk of work in one horizon) → **Steps** (tasks, sized for a single work session). For H1, the steps map onto tasks that already exist in `DECISIONS_AND_ROADMAP.md` — so this is immediately actionable, not abstract.

---

#### Section 1 — The Brain (memory & relationship)
*From: 4 stores behind `memory_graph`. To: per-user lifelong memory with consolidation.*

- **Build 1.1 (H1) — One storage story.** *(= Phase B, already planned)*
  - Steps: SQLite foundation (`db.py`) → migrate chats → migrate todos/loops/nudges/buddy → write-side `StorageRouter` → nightly backup. *(B1–B5, ready to start.)*
- **Build 1.2 (H1) — First consolidation.** Once there's a year of episodic data, turn on a basic dream-loop: nightly compress episodic → semantic, keep meaning, drop noise.
  - Steps: define what's worth keeping → summarisation pass → write to fact store via `StorageRouter` → verify recall quality didn't drop.
- **Build 1.3 (H2) — Memory that survives a model swap and a device move.** Per-user vault format; export/import; memory portable across devices.
- **Build 1.4 (H3) — Lifelong memory at scale.** Per-user sealed stores, sharded by user; consolidation tuned for multi-year horizons.

#### Section 2 — The Body (omnipresence & I/O)
*From: a browser tab + Telegram bot. To: voice-native, multi-device, ambient.*

- **Build 2.1 (H1) — Daily-driver polish.** *(= Phase C)*
  - Steps: Telegram morning-brief push → latency pass (p50 first token < 2s) → failure visibility in UI + mood. *(C1–C3.)*
- **Build 2.2 (H1→H2) — Mobile reach without a native app.** Mobile-width pass on `kitty-chat` → PWA → Tailscale access to the always-on Mac. *(= Phase E, deferred until reliability holds.)*
- **Build 2.3 (H2) — Voice-native, real-time.** Interruptible streaming voice as a first-class channel, not a toggle. (`voice_pipeline.py` is the seed.)
- **Build 2.4 (H3) — True omnipresence.** Watch, earbuds, car, glasses; pick up the thread cross-device. Native app *only if* always-listening voice becomes the core use case.

#### Section 3 — The Hands (agency)
*From: TaskPanel agent types. To: reliable real-world action with judgment.*

- **Build 3.1 (H1) — One background agent that's actually read.** *(= Phase D)* A scheduled researcher/monitor digest that produces output Jacob reads unattended. (`researcher.py`, `web_monitor.py`, `cron.py` exist.)
  - Steps: pick the one digest → schedule it → deliver via brief → measure if it's actually read → keep or kill.
- **Build 3.2 (H2) — Act-vs-ask judgment.** A reliable policy: silently handle small/reversible, ask before big/irreversible. The seed is `task_boundary.py` / `success_criteria.py`.
- **Build 3.3 (H2→H3) — Hands in the world.** Safe tool/integration framework for booking, payments, comms — gated by the judgment layer and the vault.

#### Section 4 — The Vault (privacy & security)
*From: shared-secret `auth.py` + local files. To: zero-knowledge at scale.*

- **Build 4.1 (H1) — Local-first discipline + backups.** Keep everything on-machine; encrypted nightly backups (part of B5). Keep `auth.py` enforced even on the tailnet.
- **Build 4.2 (H2) — Per-user keys & isolation.** When the second user appears, sealed per-user stores and per-user encryption from day one — never retrofit privacy.
- **Build 4.3 (H3) — Zero-knowledge + confidential compute.** Attestable enclaves for cloud-side processing; provable "we can't read it." This is the hardest build in the document and the most valuable.

#### Section 5 — The Engine (models & infra)
*From: LiteLLM fallback chain. To: tiered on-device + frontier private compute.*

- **Build 5.1 (H1) — Boring to operate.** *(= Phase A)* `kitty up` via launchd, survives reboot, `kitty doctor` green, Open WebUI remnants deleted, docs agree on ports. *(A1–A5 — the literal next thing to do.)*
- **Build 5.2 (H1) — Smart routing.** Default cheap/fast, escalate to reasoning model only when earned. (`route_model`, `domain_router` exist; tune them.)
- **Build 5.3 (H2) — On-device persona model.** Small fine-tuned/distilled model for voice, latency, privacy-sensitive ops.
- **Build 5.4 (H3) — Tiered compute at scale.** On-device default + confidential-cloud frontier escalation; vendor-swappable rental layer.

#### Section 6 — The Self (persona & trust)
*From: `SOUL.md` for one person. To: a consistent, honest, tunable companion others trust.*

- **Build 6.1 (H1) — Soul that holds under daily use.** Voice gate, drift detection, the scratchpad→approval loop already exist; keep them honest. The "no flattery / devil's advocate" trait is the product's signature — protect it.
- **Build 6.2 (H2) — Persona that generalises.** Can Kitty be *someone's* companion without being Jacob's? Tunable disposition (blunt↔gentle, quiet↔present) without losing the spine of honesty.
- **Build 6.3 (H3) — Trust at scale.** Transparency UI ("what do you know about me," edit, delete), consistent self across years and devices.

#### Section 7 — The Business (scale & monetization)
*From: a thing Jacob runs for himself. To: a paid product. Deliberately last.*

- **Build 7.1 (H2) — The first non-Jacob user.** Invite one person who isn't you. Does it work for them? This is the single most important experiment in the entire roadmap — it's the test of whether there's a company here at all.
- **Build 7.2 (H2) — Pricing & the anti-ad promise.** Subscription model; the "you are the customer, never the product" guarantee made concrete.
- **Build 7.3 (H3) — Scale economics.** Per-user cost (routing + consolidation keep it low) vs. subscription price; the unit economics that make "#1 grossing" arithmetic instead of hope.

### The dependency spine (what unblocks what)

The sections aren't independent — there's an order, and it's the order already chosen:

```
5.1 Boring to operate  ──►  1.1 One storage story  ──►  2.1 Daily-driver polish  ──►  3.1 First agent
   (Phase A)                  (Phase B)                   (Phase C)                    (Phase D)
        │                                                                                  │
        └──────────────── all of H1: prove the magic for one user ─────────────────────────┘
                                              │
                                              ▼
                            7.1 The first non-Jacob user  (the H2 gate)
                                              │
                       ┌──────────────────────┼──────────────────────┐
                       ▼                       ▼                      ▼
              4.2 Per-user keys       5.3 On-device model     2.3 Voice-native
                       │                       │                      │
                       └───────────────────────┼──────────────────────┘
                                               ▼
                                  H3: privacy at scale (4.3, 5.4) + the world
```

You cannot do 7.1 (first other user) honestly until H1 proves the magic. You cannot do H3 (the world) until 4.2/4.3 make privacy real and 5.3/5.4 make the economics work. **The gates are real — respect them, and the conservative near-term plan is revealed as the only sane way to begin.**

---

## Part 4 — The skeptic's section (read this one)

Kitty's soul says: don't give unearned agreement, steelman the opposing view, name the assumptions. So here's the honest case against everything above.

- **The relationship moat might be thinner than it looks.** If a frontier assistant can import your data and reconstruct "knowing you" in an afternoon, the compounding moat evaporates. *Defence:* the moat is privacy + trust + the *accumulated, consolidated* relationship, not just raw data — but this is the assumption most likely to be wrong, and it's worth pressure-testing early.
- **Privacy-at-scale (Build 4.3) might not be economically real.** Confidential computing at frontier-model scale may stay too expensive or too slow for years. If so, the privacy promise gets diluted, and a diluted privacy promise is no promise at all. *This is the single biggest technical risk in the document.*
- **"#1 grossing" is an outcome, not a goal you can build toward directly.** It's the score, not the game. The game is "is one person's life genuinely better." Aim at the score and you'll build growth hacks; aim at the game and the score *might* follow. The roadmap above deliberately aims at the game.
- **The author-is-the-only-user trap.** A companion that's perfect for Jacob may be perfect *because* it's Jacob's, and generalise to nobody. Build 7.1 (the first other user) exists to find this out as early as honestly possible — but it can't happen until H1 is real, which means we won't know for a while. Sit with that.
- **Beautiful architecture is a great hiding place.** (Straight from the soul file.) This entire document is, itself, a risk: it's a beautiful 10-year vision, and the danger is that admiring it becomes a substitute for shipping Phase A. The vision is only worth writing if it makes the small next step *more* likely, not less.

So the skeptic's verdict: the thesis is sound *and* the only honest way to test it is to ignore it for now and go make Kitty boring to operate for one user. Which brings us to —

---

## Part 5 — What this changes about Monday: nothing, and that's the point

The smallest real next step has not moved. It's still **Build 5.1 / Phase A — make Kitty boring to operate**: one `kitty up` command via launchd, survives a reboot, `kitty doctor` green, delete the Open WebUI remnants, make the docs agree on the port. Sized at about a week, mostly deletion and wiring of code that already exists (tasks A1–A5 in `DECISIONS_AND_ROADMAP.md`).

What this document adds is not a new task. It's a reason. Every boring reliability chore in H1 is now legibly the first brick of the thing that, if the bet is right, becomes the most personal software in the world. The grand vision and the humble next step are the same path walked from opposite ends — and they meet at `kitty up`.

> **Where I land:** The vision is worth having on paper because it tells us *why* the unglamorous near-term plan is the right one — and it does it without changing a single near-term decision. Build the magic for one. Prove it's real. Only then, the few. Only then, the world.
