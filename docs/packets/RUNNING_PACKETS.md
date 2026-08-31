# Running packets — the operator's page

For Jacob. Every command here was run before it was written down.

A **packet** is one bounded job. An **initiative** is a stack of packets that
finish one part of Kitty. You load an initiative, then Builder works through it.

---

## Before you load anything

```bash
cd ~/Projects/kitty
./kitty builder initiative doctor --json
```

You want `"ok": true` and `"fail": 0`. Warnings are fine — a warning usually
just lists initiatives someone paused on purpose.

Then check nothing stale is waiting to jump the queue:

```bash
./kitty builder supervisor status --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(len([i for i in d['initiatives'] if i.get('eligible_packets') and i['derived_state']=='active']))"
```

That prints how many old jobs Builder could pick right now. You want **0**
before you load new work. If it is not zero, Builder will pick one of those
before your new work.
That is what happened in August, when Builder spent nine tries on a job nobody
had asked for. Park anything stale:

```bash
./kitty builder initiative pause <initiative-id>
```

That is reversible — `resume` puts it back.

---

## Load a wave of packets

Check it first. This changes nothing:

```bash
python3 scripts/packet_preflight.py docs/initiatives/<file>.json
./kitty builder initiative apply docs/initiatives/<file>.json --dry-run
```

The first one refuses packets that would waste a run — mostly packets that
forbid the very file they ask to be built. Fix anything it calls an ERROR
before going further; a warning is a judgement call.

When both are clean, load it for real:

```bash
./kitty builder initiative apply docs/initiatives/<file>.json
```

That creates one job per packet. It does not start anything yet.

---

## Press go

**One packet, watching it:**

```bash
./kitty builder initiative run <initiative-id> --free
```

Free is the default and it is enforced in code — the free lane refuses a paid
model even if something tries to sneak one in. It tries seven free models in
order before giving up.

**Overnight, unattended:**

Nothing to press. A scheduled job already wakes every 15 minutes and picks up
eligible work. It is a launchd agent called `com.kitty.builder.supervisor`.
Confirm it is loaded:

```bash
launchctl list | grep kitty.builder
```

To run one round by hand instead of waiting:

```bash
./kitty builder supervisor tick
```

**When free is not enough:**

```bash
./kitty builder initiative run <initiative-id> --paid --tier cheap
```

Spending is capped at **CAD 6.00 a week** by `config/compute_governor.json`,
and the governor refuses to pay twice for the same packet at the same commit.
Use paid when free models have already failed the same packet twice with clean
failures — a provider outage is not a clean failure and tells you nothing.

---

## Watching it

```bash
./kitty builder initiative status <initiative-id> --json   # which packet is where
./kitty builder queue status --json                        # totals by state
./kitty builder queue runs --json                          # every run and how it ended
tail -f logs/builder/supervisor.log                        # the scheduler, live
```

Per-run detail, including the worker's own output:

```bash
./kitty builder queue show-run <run-id> --json
cat data/kittybuilder/runs/<run-id>/combined.log
```

---

## When something stops

**"scope_violation"** — the worker wrote a file the packet did not allow. The
job is blocked and the attempt is spent; this is not automatically repairable.
The packet is wrong, not the worker. Add the directory to that packet's
`allowed_paths` and load a corrected version. `scripts/packet_preflight.py`
catches this before it happens, which is the whole reason it exists.

**"all configured free worker providers were unavailable"** — nothing was wrong
with the work; every free model was down or rate-limited. Try again later. Do
not spend money over this.

**A timeout with no result file** — the worker ran out of its ten minutes.
Usually the packet was too big. Split it.

**Out of attempts** — grant exactly one more, deliberately:

```bash
./kitty builder initiative grant-attempt <initiative-id> <packet-id> --reason "why"
```

The reason is required and cannot be blank — it is how the next person knows
the retry was a decision rather than a reflex.

**Stop everything, right now:**

```bash
export KITTY_BUILDER_QUEUE_ENABLED=0
```

Every command that would change the queue is refused while that is set. Unset
it to re-enable. To stop the overnight schedule as well:

```bash
launchctl unload ~/Library/LaunchAgents/com.kitty.builder.supervisor.plist
```

---

## What Builder will never do on its own

It cannot push, open a pull request, or merge. It cannot touch your secrets,
your session files, or anything under `data/`. Publishing is yours alone, every
time. If something claims a packet "shipped", check GitHub — not the report.
