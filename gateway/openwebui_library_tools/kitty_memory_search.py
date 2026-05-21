"""Open WebUI tool — search Kitty's memory store via the gateway."""
import requests

GATEWAY_URL = "http://127.0.0.1:8000"


class Tools:
    def search_memory(self, query: str, limit: int = 5) -> str:
        """Search Kitty's memory for relevant information."""
        try:
            resp = requests.get(
                f"{GATEWAY_URL}/search",
                params={"q": query, "limit": limit},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("memories", [])
                if not results:
                    return "No memories found."
                lines = []
                for r in results:
                    lines.append(f"[{r.get('source', '?')}] {r.get('text', '')}")
                return "\n".join(lines)
            return f"Gateway returned {resp.status_code}."
        except Exception as exc:
            return f"Memory search failed: {exc}"
