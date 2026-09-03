# OK-LIBRARY-01 — Library Supports Ingest → Find → Open → Use

**Status:** draft candidate; not activated
**Roadmap phase:** 2 — primary surfaces

## Mission
Make Library a dependable place to put information and get it back into real work even when indexing or one retrieval source is degraded.

## Depends on
- `KF-SEARCH-01` for truthful all-store search where still missing.
- Artifact/knowledge/index authorities remain separate but explicitly represented.
- `OK-CONTINUITY-01` for Project/Chat/Artifact relationships.

## Product acceptance moment
Add a document/file/URL, watch its real ingest/index state, find it later, open the content/metadata, attach/reference it in Chat or a Project, and recover intelligibly if indexing or source content is unavailable.

## Required behavior
- Ingest paths enforce bounded input behavior and show acceptance/rejection in product language.
- Distinguish at least: saved, indexing, indexed/searchable, indexing failed, source/content unavailable, and deleted/removed when supported.
- An artifact/document that is saved remains visible even when semantic indexing is down.
- Search reports the stores it truly searched; source failure is not silently interpreted as “no results.”
- Open uses the canonical Artifact/document representation and preserves useful metadata/provenance.
- `Ask Kitty`/attach-to-chat passes a durable reference, not a pasted internal ID or giant raw content dump.
- Associate/add-to-Project uses the existing relationship authority and is visible from the intended surfaces after refresh.
- Destructive removal keeps its real approval/confirmation boundary and does not strand downstream references silently.

## Verification
**Tier 1:** Library/search/artifact/ingest tests; add indexed-vs-saved and partial-source regressions.

**Tier 2:** desktop + iPhone-class running app: ingest one supported source, find/open it, use it in Chat or Project, then repeat the search/open path with indexing unavailable and with content unavailable.

**Tier 3:** independent reviewer proves the saved item survives the degraded index path and can still be used through a canonical reference.

## Non-goals
- Replacing the vector/index system.
- A new document database.
- Unlimited file-format support.

## Done when
Library is useful as both storage and retrieval, and a degraded index cannot make saved user content appear to have vanished.
