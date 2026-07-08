import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger("kitty.sse")

class SSEBroadcaster:
    def __init__(self):
        self.queues: dict[str, asyncio.Queue] = {}
        self.loop = None

    async def subscribe(self, session_id: str) -> AsyncGenerator[str, None]:
        if self.loop is None:
            self.loop = asyncio.get_running_loop()

        # Clean up old connection for same session
        if session_id in self.queues:
            try:
                self.queues[session_id].put_nowait(None)
            except Exception:
                pass

        q = asyncio.Queue()
        self.queues[session_id] = q
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    if msg is None:
                        # Replaced by new connection
                        break
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if self.queues.get(session_id) is q:
                del self.queues[session_id]

    def broadcast(self, message: str):
        """Thread-safe broadcast to all connected SSE clients."""
        if not self.queues or self.loop is None:
            return

        for q in list(self.queues.values()):
            try:
                self.loop.call_soon_threadsafe(q.put_nowait, message)
            except Exception as e:
                logger.error("SSE broadcast error: %s", e)

broadcaster = SSEBroadcaster()
