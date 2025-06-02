from compendium_agent.agent import agent_executor, config
from langchain_core.messages import HumanMessage

from compendium_agent.agent import agent_executor, config
from langchain_core.messages import HumanMessage
import nest_asyncio; nest_asyncio.apply()

msgs = [
    HumanMessage(content="Ich bin Apotheker in Bern."),
    HumanMessage(content="Kann ich Dafalgan Dolo 500 mg in der Schwangerschaft nehmen?")
]

for m in msgs:
    for step in agent_executor.stream({"messages": [m]}, config, stream_mode="values"):
        print("➡️", step["messages"][-1].content, flush=True)