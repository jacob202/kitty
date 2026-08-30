# Kitty — Codemap

A read-instead-of-grep mental model of the codebase. Five lenses, each
viewing the whole system from one perspective. Pick the lens that matches
the question you have, not the code you want to find.

| Lens                                  | Use when you want to know                            |
| ------------------------------------- | ---------------------------------------------------- |
| [00-overview](00-overview.md)         | What is Kitty, in one page                           |
| [10-capabilities](10-capabilities.md) | What can I ask Kitty to do                           |
| [20-dataflow](20-dataflow.md)         | Where does my data go, who reads it back             |
| [30-codemap](30-codemap.md)           | How is the code laid out, what depends on what       |
| [40-domain](40-domain.md)             | What's a `signal`, a `project`, a `tier` — the nouns |

Each doc is **conceptual, not a file listing.** It names modules and
edges at the level you reason about them ("the gateway dispatches LLM
calls"), not at the level you grep for them ("`gateway/llm_client.py`
defines `call_llm`").

If a doc references a file path, that's a sign you should open the
file — but the doc itself should still make sense without you opening
it.

> Diagrams use Mermaid. They are illustrative; if a doc disagrees with
> the code, the code is right and the doc is wrong — fix the doc.
