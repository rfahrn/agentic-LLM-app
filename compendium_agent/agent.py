# compendium_agent/agent.py


from model import model
from memory import memory
from tools.tavily_tool_ import tavily_tool, run_tavily_search
from tools.compendium_tool import get_compendium_info_with_scraping
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain.tools import Tool

# Define the scraping tool, passing the Tavily tool for internal querying
CompendiumScrapingTool = Tool(
    name="Compendium.ch Scraper",
    func=lambda x: get_compendium_info_with_scraping(x),
    description="Scraped pharmazeutische Informationen von Compendium.ch Produktseiten"
)

# List of tools for the agent to use
tools = [tavily_tool, CompendiumScrapingTool]

# Create agent executor using LangGraph
agent_executor = create_react_agent(model, tools, checkpointer=memory)

# Agent configuration (used for memory threading)
config = {"configurable": {"thread_id": "compendium-fast-001"}}
