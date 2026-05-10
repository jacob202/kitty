import requests


class N8nTrigger:
    def __init__(self, webhook_url="http://localhost:5678/webhook"):
        self.webhook_url = webhook_url.rstrip("/")

    def trigger(self, workflow_name, data):
        url = f"{self.webhook_url}/{workflow_name}"
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"error": "n8n not running. Start with: n8n start"}
        except Exception as e:
            return {"error": str(e)}
