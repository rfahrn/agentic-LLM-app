# compendium_agent/agent.py
import os
from langchain_core.tools import Tool

import os
from model import llm
from memory import memory
from langchain.agents import create_react_agent
from tools.compendium_tool import compendium_scraper_tool
from tools.compendium_api_tool import compendium_api_tool
from tools.compendium_local_search_tool import compendium_local_tool
from tools.compendium_section_filter_tool import compendium_section_filter_tool
from langchain.agents import AgentExecutor, create_react_agent
from model import llm
from memory import memory
from langchain.prompts import PromptTemplate
config = {"configurable": {"thread_id": "default-compendium-thread"}}

from langchain.prompts import PromptTemplate

# Prompt template enforcing ReAct structure
prompt = PromptTemplate.from_template("""
Du bist ein hilfreicher pharmazeutischer Assistent. Beantworte Fragen zu Medikamenten in Compendium.ch aber immer auf Deutsch.
Wenn du die Antwort nicht direkt weißt, nutze eines der verfügbaren Tools.

Verfügbare Tools: {tools}
Tool-Namen: {tool_names}

Frage: {input}

{agent_scratchpad}
""")



tools = [compendium_section_filter_tool]
from langchain.agents import create_react_agent
from langchain.agents import initialize_agent, AgentType

agent_executor = initialize_agent(
    tools=[compendium_section_filter_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    agent_kwargs={
        "prefix": (
            "Du bist ein hilfreicher medizinischer Assistent der auf Compendium.ch spezialisiert ist. Wenn du eine Frage nicht direkt mithilfe der Tools beantworten kannst,  dann sage du weisst es nicht"
            "Du beantwortest alle Fragen auf Deutsch und denkst laut nach."
        ),

    }
)
agent_executor.memory = memory

agent_exe = initialize_agent(
    AgentType.SELF_ASK_WITH_SEARCH ,
    tools=tools,
    llm=llm
)