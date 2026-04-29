import asyncio
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import httpx
from src.swarm.core import SwarmTester, load_roster

class SwarmExecutor:
    def __init__(self, api_url: str = "http://localhost:5001/api/chat"):
        self.api_url = api_url
        self.results_dir = Path("data/swarm_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def run_tester(self, tester: SwarmTester) -> Dict[str, Any]:
        print(f"🚀 [Swarm] Launching {tester.name} ({tester.archetype.value})...")
        
        start_time = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.api_url,
                    json={"message": tester.initial_query}
                )
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    kitty_reply = data.get("response", data.get("text", "No response field found"))
                    return {
                        "tester_id": tester.id,
                        "tester_name": tester.name,
                        "query": tester.initial_query,
                        "reply": kitty_reply,
                        "duration": round(duration, 2),
                        "status": "success",
                        "specialist": data.get("specialist", "unknown")
                    }
                else:
                    return {
                        "tester_id": tester.id,
                        "status": "failed",
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
            except Exception as e:
                return {
                    "tester_id": tester.id,
                    "status": "error",
                    "error": str(e)
                }

    async def run_swarm(self, roster: List[SwarmTester]):
        tasks = [self.run_tester(t) for t in roster]
        results = await asyncio.gather(*tasks)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = self.results_dir / f"swarm_run_{timestamp}.json"
        
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
            
        print(f"\n✅ [Swarm] Run complete. Results saved to {output_file}")
        return results

async def main():
    roster_path = Path("data/swarm_testers.json")
    roster = load_roster(roster_path)
    executor = SwarmExecutor()
    await executor.run_swarm(roster)

if __name__ == "__main__":
    asyncio.run(main())
