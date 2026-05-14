## 2025-05-14 - Prevent synchronous file I/O from blocking asyncio main thread
**Learning:** Found that `ReadFileTool` and `WriteFileTool` executed synchronous file I/O operations (`path.read_text()`, `path.write_text()`, `mkdir()`) inside `async def execute`. This blocked the asyncio event loop, causing a performance bottleneck, especially when scaling agents.
**Action:** Wrapped these disk I/O operations in `asyncio.to_thread()` to offload them to worker threads, ensuring the main asyncio event loop remains free for other concurrent tasks.
