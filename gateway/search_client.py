
import requests
import logging
from gateway.config import OWUI_URL, OWUI_ADMIN_EMAIL, OWUI_ADMIN_PASSWORD, get_owui_headers

logger = logging.getLogger("kitty.search_client")

class OpenWebUISearchClient:
    def __init__(self):
        self.url = OWUI_URL
        self.token = self._login()
        self.kb_map = self._get_kb_map()

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

    def search_kb(self, kb_name: str, query: str, k: int = 5) -> str:
        """
        Performs a vector search against a specific knowledge base via HTTP.
        """
        kb_id = self.kb_map.get(kb_name.lower())
        if not kb_id:
            # Refresh map once in case a new KB was added
            self.kb_map = self._get_kb_map()
            kb_id = self.kb_map.get(kb_name.lower())
            
        if not kb_id:
            logger.warning(f"KB not found: {kb_name}. Available: {list(self.kb_map.keys())}")
            return f"Error: Knowledge Base '{kb_name}' not found."

        try:
            payload = {
                "collection_names": [kb_id],
                "query": query,
                "k": k
            }
            
            resp = requests.post(
                f"{self.url}/api/v1/retrieval/query/collection",
                headers=get_owui_headers(self.token),
                json=payload,
                timeout=60
            )
            
            if resp.status_code == 400:
                logger.error(f"OWUI Search 400 Detail: {resp.text}")
                return f"Error 400: Malformed search request to {kb_name}."
                
            resp.raise_for_status()
            results = resp.json()
            
            context_blocks = []
            for hit in results.get("results", []):
                content = hit.get("content", "")
                # Some versions of OWUI return metadata in 'metadata', others in 'meta'
                meta = hit.get("metadata") or hit.get("meta") or {}
                source = meta.get("source", "Unknown")
                context_blocks.append(f"[Source: {source}]\n{content}")
            
            return "\n\n---\n\n".join(context_blocks) if context_blocks else "No relevant context found."
            
        except Exception as e:
            logger.error(f"Search failed for {kb_name}: {e}")
            return f"Error during search: {str(e)}"

# Singleton instance
search_client = OpenWebUISearchClient()

if __name__ == "__main__":
    # Quick test
    res = search_client.search_kb("electronics", "How to fix a mosfet?")
    print(res)
