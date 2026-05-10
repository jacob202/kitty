class WebSearch:
    def __init__(self, api_key=""):
        self.api_key = api_key
        self._client = None
        if api_key and api_key != "YOUR_TAVILY_KEY":
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=api_key)
            except ImportError:
                print("[WebSearch] tavily-python not installed. Run: pip install tavily-python")

    def search(self, query, max_results=5):
        if not self._client:
            return [{"error": "Tavily API key not configured. Add tavily_api_key to config.json."}]
        try:
            response = self._client.search(query, max_results=max_results)
            return [
                {"title": r["title"], "url": r["url"], "content": r["content"]}
                for r in response.get("results", [])
            ]
        except Exception as e:
            return [{"error": str(e)}]
