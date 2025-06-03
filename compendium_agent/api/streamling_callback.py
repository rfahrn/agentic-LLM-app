# compendium_agent/streaming_callback.py
from langchain.callbacks.base import AsyncCallbackHandler

class StreamingHandler(AsyncCallbackHandler):
    def __init__(self, queue):
        self.queue = queue

    async def on_agent_action(self, action, **kwargs):
        await self.queue.put(f"data: 🤔 Thought: {action.log}\n\n")
        await self.queue.put(f"data: 🛠️ Action: {action.tool}\n\n")
        await self.queue.put(f"data: 🔧 Input: {action.tool_input}\n\n")

    async def on_tool_end(self, output, **kwargs):
        await self.queue.put(f"data: 👀 Observation: {output}\n\n")

    async def on_llm_end(self, response, **kwargs):
        pass  # Optionally handle model completions

    async def on_chain_end(self, outputs, **kwargs):
        answer = outputs.get('output') or str(outputs)
        await self.queue.put(f"data: ✅ Final Answer: {answer}\n\n")
