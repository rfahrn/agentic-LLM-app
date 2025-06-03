from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import agent_executor, config
from langchain_core.messages import HumanMessage
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from agent import agent_executor, config
import asyncio
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

    async def on_chat_model_start(self, *args, **kwargs):
        pass  # Fixes NotImplementedError in LangGraph


    async def on_chain_end(self, outputs, **kwargs):
        answer = outputs.get('output') or str(outputs)
        await self.queue.put(f"data: ✅ Final Answer: {answer}\n\n")
    

app = FastAPI()
app.mount("/static", StaticFiles(directory="api/static"), name="static")
templates = Jinja2Templates(directory="api/templates")

class PromptRequest(BaseModel):
    prompt: str

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/query")
async def query(request: PromptRequest):
    prompt = request.prompt
    queue = asyncio.Queue()
    handler = StreamingHandler(queue)

    async def event_generator():
        try:
            task = asyncio.create_task(agent_executor.ainvoke(
                [HumanMessage(content=prompt)],
                config={**config, "callbacks": [handler]}
            ))

            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield f"data: {message}\n\n"
                    if "✅ Final Answer:" in message:
                        break
                except asyncio.TimeoutError:
                    if task.done():
                        break

        except Exception as e:
            yield f"data: ❌ Fehler: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")