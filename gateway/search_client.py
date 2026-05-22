import requests
import logging
import os
import re

from gateway.config import OWUI_URL, OWUI_ADMIN_EMAIL, OWUI_ADMIN_PASSWORD, get_owui_headers
from gateway.llm_client import call_llm
from gateway.registry import get_collection_id

logger = logging.getLogger("kitty.search_client")

LOW_CONFIDENCE_THRESHOLD = 0.75
HYDE_MODEL = os.environ.get("KITTY_HYDE_MODEL", "gpt-4o-mini")

class OpenWebUISearchClient:
    def __init__(self):
        self.url = OWUI_URL
        self.token = self._login()
        self.kb_map = self._get_kb_map()

    def _ensure_session(self):
        if self.token:
            return True
        self.token = self._login()
        if not self.token:
            return False
        self.kb_map = self._get_kb_map()
        return bool(self.token)

    def _login(self):
        try:
            resp = requests.post(
                f"{self.url}/api/v1/auths/signin", 
                json={"email": OWUI_ADMIN_EMAIL, "password": OWUI_ADMIN_PASSWORD}, 
                timeout=20
            )
            resp.raise_for_status()
            return resp.json().get("token")
        except Exception as e:
            logger.error(f"OWUI Login failed at {self.url}: {e}")
            return None

    def _get_kb_map(self):
        if not self.token: return {}
        try:
            resp = requests.get(
                f"{self.url}/api/v1/knowledge/", 
                headers=get_owui_headers(self.token), 
                timeout=20
            )
            resp.raise_for_status()
            data = resp.json()
            items = data["items"] if isinstance(data, dict) else data
            return {item["name"].lower(): item["id"] for item in items}
        except Exception as e:
            logger.error(f"Failed to fetch KBs from {self.url}: {e}")
            return {}

    def _result(self, kb_name: str, query: str, *, kb_id=None, status="ok", summary="", hits=None, error=None):
        hits = hits or []
        sources = []
        seen_sources = set()
        for hit in hits:
            meta = hit.get("metadata") or hit.get("meta") or {}
            source = meta.get("source", "Unknown")
            if source in seen_sources:
                continue
            seen_sources.add(source)
            sources.append(source)
        return {
            "kb_name": kb_name,
            "kb_id": kb_id,
            "query": query,
            "status": status,
            "summary": summary,
            "hits": hits,
            "hit_count": len(hits),
            "sources": sources,
            "method_used": "vector",
            "error": error,
        }

    def _tokenize_keywords(self, query: str) -> list[str]:
        raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/.]{1,}", query or "")
        tokens = []
        seen = set()
        for token in raw_tokens:
            normalized = token.strip().lower()
            if len(normalized) < 3:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(normalized)
        return tokens

    def _build_summary(self, hits):
        context_blocks = []
        for hit in hits:
            content = hit.get("content", "")
            meta = hit.get("metadata") or hit.get("meta") or {}
            source = meta.get("source", "Unknown")
            context_blocks.append(f"[Source: {source}]\n{content}")
        return "\n\n---\n\n".join(context_blocks) if context_blocks else "No relevant context found."

    def _hit_chunk_id(self, hit):
        meta = hit.get("metadata") or hit.get("meta") or {}
        for key in ("chunk_id", "id", "uuid", "hash", "source"):
            value = meta.get(key)
            if value:
                return str(value)
        content = hit.get("content", "")
        return f"{meta.get('source', 'unknown')}::{hash(content)}"

    def _normalize_hits(self, payload):
        if not isinstance(payload, dict):
            return []

        if isinstance(payload.get("results"), list):
            return payload["results"]

        documents = payload.get("documents") or []
        metadatas = payload.get("metadatas") or []
        distances = payload.get("distances") or []
        hits = []

        for row_index, row_docs in enumerate(documents):
            if not isinstance(row_docs, list):
                continue
            row_metas = metadatas[row_index] if row_index < len(metadatas) and isinstance(metadatas[row_index], list) else []
            row_distances = distances[row_index] if row_index < len(distances) and isinstance(distances[row_index], list) else []

            for col_index, content in enumerate(row_docs):
                metadata = row_metas[col_index] if col_index < len(row_metas) and isinstance(row_metas[col_index], dict) else {}
                hit = {
                    "content": content or "",
                    "metadata": metadata,
                }
                if col_index < len(row_distances):
                    hit["distance"] = row_distances[col_index]
                hits.append(hit)

        return hits

    def _hyde_query(self, query: str) -> str:
        prompt = (
            "Write a single-sentence hypothetical answer that would likely appear in a technical manual "
            "or troubleshooting guide for this user query. Be concrete and retrieval-friendly.\n\n"
            f"Query: {query}"
        )
        answer = call_llm(
            messages=[{"role": "user", "content": prompt}],
            model=HYDE_MODEL,
            max_tokens=80,
            temperature=0,
            operation="search.hyde",
            metadata={"feature": "hyde_retrieval"},
        ).strip()
        return answer or query

    def _vector_search(self, kb_id: str, query: str, k: int):
        payload = {
            "collection_names": [kb_id],
            "query": query,
            "k": k,
        }
        resp = requests.post(
            f"{self.url}/api/v1/retrieval/query/collection",
            headers=get_owui_headers(self.token),
            json=payload,
            timeout=60
        )
        return payload, resp

    def _keyword_search(self, kb_id: str, kb_name: str, query: str, k: int):
        tokens = self._tokenize_keywords(query)
        if not tokens:
            return []

        resp = requests.get(
            f"{self.url}/api/v1/knowledge/{kb_id}/files",
            headers=get_owui_headers(self.token),
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", []) if isinstance(data, dict) else []

        scored_hits = []
        for item in items:
            content = ((item.get("data") or {}).get("content") or "").strip()
            filename = item.get("filename") or ((item.get("meta") or {}).get("name")) or "Unknown"
            haystack = f"{filename}\n{content}".lower()
            score = sum(1 for token in tokens if token in haystack)
            if score == 0:
                continue
            scored_hits.append(
                {
                    "content": content[:4000],
                    "metadata": {
                        "source": filename,
                        "chunk_id": item.get("id") or filename,
                        "match_score": score,
                        "collection_id": kb_id,
                        "kb_name": kb_name,
                    },
                    "score": score,
                }
            )

        scored_hits.sort(key=lambda hit: hit.get("score", 0), reverse=True)
        return scored_hits[:k]

    def _merge_hits(self, vector_hits, keyword_hits):
        merged = []
        seen = set()
        for hit in list(vector_hits) + list(keyword_hits):
            chunk_id = self._hit_chunk_id(hit)
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            merged.append(hit)
        return merged

    def search_kb(self, kb_name: str, query: str, k: int = 5, use_hyde: bool = False) -> str:
        """
        Performs a vector search against a specific knowledge base via HTTP.
        """
        if not self._ensure_session():
            result = self._result(
                kb_name,
                query,
                status="auth_error",
                summary="Error: Open WebUI authentication unavailable.",
                error="authentication unavailable",
            )
            result["method_used"] = "vector"
            return result

        try:
            kb_id = get_collection_id(kb_name)
        except KeyError as exc:
            logger.warning("KB not found in registry: %s", kb_name)
            result = self._result(
                kb_name,
                query,
                status="kb_not_found",
                summary=f"Error: Knowledge Base '{kb_name}' not found.",
                error=str(exc),
            )
            result["method_used"] = "vector"
            return result

        try:
            vector_query = self._hyde_query(query) if use_hyde else query
            method_used = "hyde+vector" if use_hyde else "vector"
            payload, resp = self._vector_search(kb_id, vector_query, k)

            if resp.status_code == 401:
                logger.warning("OWUI token expired; retrying search after re-auth")
                self.token = None
                if not self._ensure_session():
                    result = self._result(
                        kb_name,
                        query,
                        kb_id=kb_id,
                        status="auth_error",
                        summary="Error: Open WebUI authentication unavailable.",
                        error="authentication unavailable",
                    )
                    result["method_used"] = method_used
                    return result
                payload, resp = self._vector_search(kb_id, vector_query, k)
            
            if resp.status_code == 400:
                logger.error(f"OWUI Search 400 Detail: {resp.text}")
                result = self._result(
                    kb_name,
                    query,
                    kb_id=kb_id,
                    status="bad_request",
                    summary=f"Error 400: Malformed search request to {kb_name}.",
                    error=resp.text,
                )
                result["method_used"] = method_used
                return result
                
            resp.raise_for_status()
            results = resp.json()
            vector_hits = self._normalize_hits(results)
            best_distance = min(
                (
                    hit.get("distance")
                    for hit in vector_hits
                    if isinstance(hit.get("distance"), (int, float))
                ),
                default=None,
            )

            keyword_hits = []
            keyword_attempted = False
            if not vector_hits or (best_distance is not None and best_distance > LOW_CONFIDENCE_THRESHOLD):
                keyword_attempted = True
                try:
                    keyword_hits = self._keyword_search(kb_id, kb_name, query, k)
                except Exception as keyword_error:
                    logger.warning("Keyword fallback failed for %s: %s", kb_name, keyword_error)
                    keyword_hits = []
                if keyword_hits or keyword_attempted:
                    method_used = "keyword_fallback"

            hits = self._merge_hits(vector_hits, keyword_hits)
            summary = self._build_summary(hits)
            result = self._result(
                kb_name,
                query,
                kb_id=kb_id,
                status="ok",
                summary=summary,
                hits=hits,
            )
            result["method_used"] = method_used
            return result
            
        except Exception as e:
            logger.error(f"Search failed for {kb_name}: {e}")
            result = self._result(
                kb_name,
                query,
                kb_id=kb_id,
                status="search_error",
                summary=f"Error during search: {str(e)}",
                error=str(e),
            )
            result["method_used"] = "hyde+vector" if use_hyde else "vector"
            return result

# Singleton instance
search_client = OpenWebUISearchClient()

if __name__ == "__main__":
    # Quick test
    res = search_client.search_kb("electronics", "How to fix a mosfet?")
    print(res)
