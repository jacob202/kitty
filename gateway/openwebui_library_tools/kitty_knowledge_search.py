"""Open WebUI tool — search Kitty's knowledge base via the gateway."""
import requests

GATEWAY_URL = "http://127.0.0.1:8000"


class Tools:
    def search_knowledge(self, query: str, limit: int = 5) -> str:
        """Search Kitty's knowledge base for relevant information."""
        try:
            resp = requests.get(
                f"{GATEWAY_URL}/search",
                params={"q": query, "limit": limit},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("knowledge", [])
                if not results:
                    return "No knowledge found."
                lines = []
                for r in results:
                    lines.append(f"[{r.get('source', '?')}] {r.get('text', '')}")
                return "\n".join(lines)
            return f"Gateway returned {resp.status_code}."
        except Exception as exc:
            return f"Knowledge search failed: {exc}"
