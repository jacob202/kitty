# Socratic Lens - Context Grammar Induction (CGI)

**A dynamic method for detecting transformative questions in any corpus.**

---

## The Problem

How do you know if a question is "good"?

Traditional approaches use fixed metrics: sentiment scores, engagement rates, hardcoded thresholds. But these assume we already know what "good" means.

We don't.

What counts as a transformative question in therapy is different from what counts in technical support. A question that opens depth in one context might derail another.

**The real problem isn't measuring. It's defining.**

---

## The Origin

This system began with one observation from the film *Arrival* (2016):

When humanity encounters aliens, the military asks: *"Are you hostile?"*

Louise, the linguist, asks: *"What is your purpose?"*

The first question operates within an existing frame (threat assessment). The second question **transforms the frame itself**.

This led to a simple thesis:

> **The right question is not the one that gets the best answer.**
> **The right question is the one that transforms the context.**

But then: what is "context"? And how do you detect transformation?

---

## The Insight

Context is not universal. It is **corpus-specific**.

In a therapy dataset, context might mean emotional depth.
In a technical dataset, context might mean problem scope.
In a philosophical dataset, context might mean abstraction level.

You cannot hardcode this. You must **discover** it.

---

## The Method

CGI runs six chains:

| Chain | Question |
|-------|----------|
| 1. Grammar | "What does *context* mean in this dataset?" |
| 2. Positive | "What does *transformation* look like here?" |
| 3. Negative | "What does *stagnation* look like here?" |
| 4. Lens | "What is the decision framework for this corpus?" |
| 5. Scan | "Which questions are transformative?" |
| 6. Socratic | "What did we learn? What remains for the human?" |

The key: **nothing is assumed**. The system learns from examples before it judges.

---

## What It Produces

A **lens**: a corpus-specific interpretive framework.

Example output from test run:

```
Lens: "Surface-to-Meaning Reframe Lens"

Decision Question: 
"Does this question redirect from executing/describing 
toward examining internal meaning, assumptions, or self-relation?"

Transformative Signals:
- Invites internal reflection rather than external description
- Introduces value trade-offs (money vs belonging, loss vs gain)
- Reframes stakes around identity or meaning

Mechanical Signals:
- Clarifies or advances existing task
- Requests facts without challenging frame
- Keeps intent purely instrumental
```

This lens was not programmed. It **emerged** from the data.

---

## What It Is

- A **discovery method**, not a scoring algorithm
- A **mirror**, not a judge
- **Socratic**: it asks, it doesn't conclude
- **Corpus-adaptive**: learns what "context" means locally
- **Human-final**: shows candidates, human decides

---

## What It Is NOT

- Not a replacement for human judgment
- Not a universal metric (no "0.7 = good")
- Not a classifier with fixed categories
- Not trying to define "the right question" globally
- Not assuming all corpora work the same way

---

## The Socratic Alignment

Socrates didn't give answers. He asked questions that made people **see differently**.

CGI follows this:

| Principle | Implementation |
|-----------|----------------|
| "I know that I know nothing" | Chain 1-3: Learn before judging |
| Elenchus (examination) | Chain 5: Apply lens, find tensions |
| Aporia (productive confusion) | Chain 6: What remains unresolved? |
| Human as final authority | System shows, human decides |

---

## Key Discovery from Testing

Initial assumption:
> Transformative = "asks about feelings"

Actual finding:
> Transformative = "introduces value trade-offs that force reinterpretation of stakes"

The system **corrected its own lens** through the Socratic chain.

Questions like:
- "What would you lose by taking it?"
- "What does that community give you that money can't?"

These don't just "go deeper." They **reframe what's at stake**.

---

## What Remains for Humans

The system cannot decide:

1. **Appropriateness** — Is this the right moment for depth?
2. **Safety** — Is this person ready for this question?
3. **Ethics** — Should this frame be challenged at all?
4. **Timing** — Is transformation desirable here?

These require judgment, empathy, consent. No system should pretend otherwise.

---

## Why This Matters

LLMs are increasingly used to generate questions: in therapy bots, coaching apps, educational tools, interviews.

Most evaluate questions by **engagement metrics** or **user satisfaction**.

But a question can be satisfying and still be shallow.
A question can be uncomfortable and still be transformative.

CGI offers a different lens:

> Don't ask "Did they like it?"
> Ask "Did it change how they see the problem?"

---

## The Meta-Question

During testing, the final Socratic chain asked:

> "Was this analysis process itself a transformative question?"

The answer:

> "Yes—the analysis itself functioned as a transformative inquiry. 
> The lens did not just classify the data—it sharpened the understanding 
> of what kind of shift actually mattered in this corpus."

The method practiced what it preached.

---

## Usage

```python
from cgi_runner import CGIRunner

runner = CGIRunner(llm_fn=your_llm)
results = runner.run(your_corpus)

print(results["lens"])        # Corpus-specific framework
print(results["candidates"])  # Transformative question candidates
print(results["reflection"])  # Meta-analysis
```

---

## Files

```
socratic-context-analyzer/
├── chains/
│ ├── CGI-1-GRAMMAR.yaml
│ ├── CGI-2-POSITIVE.yaml
│ ├── CGI-3-NEGATIVE.yaml
│ ├── CGI-4-LENS.yaml
│ ├── CGI-5-SCAN.yaml
│ └── CGI-6-SOCRATIC.yaml
├── tests/
│ ├── Mental Health Counseling Dataset/
│ │ ├── 10 Selected Conversation (Manuel Corpus)/
│ │ │ ├── thought process/
│ │ │ ├── cgi_manual_corpus_report.md
│ │ │ ├── cgi_manual_corpus_report_TR.md
│ │ │ └── prompt and thought process.txt
│ │ ├── Randomly Select 20 Conversation/
│ │ │ ├── thought process/
│ │ │ ├── cgi_analysis_report.md
│ │ │ ├── cgi_analysis_report_TR.md
│ │ │ └── prompt and thought process.txt
│ │ ├── 0000.parquet
│ │ ├── cgi_complete_summary_EN.md
│ │ ├── cgi_complete_summary_TR.md
│ │ └── first-test-output.txt
├── cgi_runner.py
├── PAPER.md
├── MAKALE.md
├── chain-view.text
├── gpt-instructions.md
└── test-output.text
```

---

## Closing

This project started with a simple question:

> "How do I know if a question is good?"

The answer turned out to be another question:

> "Good for what? In what context? By whose definition?"

CGI doesn't answer these. It helps you **discover** them.

That's the point.

---

## License

MIT

---