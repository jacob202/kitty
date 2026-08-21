# Vendored BFL FLUX.2 guidance — provenance

This directory vendors ONLY the black-forest-labs model-guidance material that
the Kitty `flux2@1` semantic compiler (gateway/flux2_compiler.py) actually
depends on. It is pinned, attributed, and visibly replaceable; swapping this
directory is the mechanism for an upstream refresh.

## Upstream repository

- Repository: `black-forest-labs/skills`
- Branch: `master`
- Pinned commit SHA: `a6f74cc70a85179ab74c578ed65dcf3d8dafca9e`
  (committer date 2026-08-10T20:50:43Z)
- Retrieval date: 2026-08-19

## Files taken (original repo paths → vendored path)

| Original path | Vendored path |
| --- | --- |
| `skills/flux-image-best-practices/SKILL.md` | `skills/flux-image-best-practices/SKILL.md` |
| `skills/flux-image-best-practices/rules/core-principles.md` | `skills/flux-image-best-practices/rules/rules-core-principles.md` |
| `skills/flux-image-best-practices/rules/flux2-models.md` | `skills/flux-image-best-practices/rules/rules-flux2-models.md` |
| `skills/flux-image-best-practices/rules/t2i-prompting.md` | `skills/flux-image-best-practices/rules/rules-t2i-prompting.md` |
| `skills/flux-image-best-practices/rules/i2i-prompting.md` | `skills/flux-image-best-practices/rules/rules-i2i-prompting.md` |
| `skills/flux-image-best-practices/rules/multi-reference-editing.md` | `skills/flux-image-best-practices/rules/rules-multi-reference-editing.md` |
| `skills/flux-image-best-practices/rules/negative-prompt-alternatives.md` | `skills/flux-image-best-practices/rules/rules-negative-prompt-alternatives.md` |
| `skills/flux-image-best-practices/rules/hex-color-prompting.md` | `skills/flux-image-best-practices/rules/rules-hex-color-prompting.md` |
| `skills/bfl-api/SKILL.md` | `skills/bfl-api/SKILL.md` |

Not vendored (whole-repo copy avoided on purpose): the rest of the skills tree.

## License assertion

The upstream README states the repository is MIT licensed. The upstream
repository has NO root LICENSE file at the pinned commit, so there is no
license text to copy here. Per ADR 0040 decision 9, record the pinned commit
and the license assertion, and re-check before any commercial distribution.
Companion licensing fact: `black-forest-labs/flux2` (model/framework repo) is
Apache-2.0.

## Usage contract

- The compiler consumes these files as the model-specific knowledge source.
- No upstream file may be edited in place; a refresh replaces the whole
  directory at a new pinned commit and updates this provenance file and the
  `COMPILER_GUIDANCE_RETRIEVED_AT` constant in the compiler.