import asyncio
import time
from src.memory.chroma_store import ChromaMemoryStore
from src.core.types import MemoryEntry
import tempfile
import uuid
import os

async def benchmark():
    with tempfile.TemporaryDirectory() as d:
        store = ChromaMemoryStore(persist_directory=d)

        # Store some data
        await store.store(MemoryEntry(agent_id="agent_1", content="Hello world", entry_id=str(uuid.uuid4())))

        # Create a background task that just yields
        async def background_task():
            counter = 0
            while True:
                await asyncio.sleep(0.001)
                counter += 1

        # Measure concurrent searches
        async def concurrent_searches(n):
            tasks = []
            for _ in range(n):
                tasks.append(store.search(agent_id="agent_1", query="Hello"))
            await asyncio.gather(*tasks)

        # Let's measure event loop blocking by having a background ticker
        ticker_count = 0
        async def ticker():
            nonlocal ticker_count
            while True:
                await asyncio.sleep(0)
                ticker_count += 1

        ticker_task = asyncio.create_task(ticker())

        start = time.time()
        await concurrent_searches(100)
        end = time.time()

        ticker_task.cancel()

        print(f"Time taken for 100 concurrent searches: {end - start:.4f}s")
        print(f"Event loop ticks during this time: {ticker_count}")

asyncio.run(benchmark())
