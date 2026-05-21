import asyncio
import os
import sys
sys.path.insert(0, os.getcwd())
from gateway.ingestion_queue import process_queue
if __name__ == "__main__":
    asyncio.run(process_queue())
