#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from src.swarm.executor import main as run_swarm

if __name__ == "__main__":
    print("🐾 [Kitty Swarm] Initializing Tester Swarm...")
    
    # Check if kitty is running
    # If not, we should probably warn or start it, but for now we assume it's up
    # as per user instruction "start kitty ad start testing"
    
    try:
        asyncio.run(run_swarm())
    except KeyboardInterrupt:
        print("\n🛑 Swarm interrupted.")
    except Exception as e:
        print(f"❌ Swarm failed: {e}")
