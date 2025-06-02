# compendium_agent/tools/tavily_tool_.py
from langchain_community.tools.tavily_search import TavilySearchResults

# Define the tool instance
tavily_tool = TavilySearchResults(k=5)

# Optional: if you want a wrapper function
def run_tavily_search(query: str):
    return tavily_tool.run(query)
