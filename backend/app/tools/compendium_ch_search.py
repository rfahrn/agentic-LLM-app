
from tavily import TavilyClient
import os
import streamlit as st


#api_key_tavily = st.secrets["tavily"]["TAVILY_API_KEY"]
api_key_tavily = os.getenv("TAVILY_API_KEY")
client = TavilyClient(api_key=api_key_tavily)

def get_compendium_info(medication: str) -> str:
    """Search medication info via Compendium.ch"""
    query = f"site:compendium.ch {medication}"
    results = client.search(query=query, search_depth="advanced", include_answer=True)
    
    answer = results.get("answer")
    urls = [r["url"] for r in results.get("results", [])]

    if not answer:
        return (
            f"⚠️ Keine direkte Antwort gefunden.\n\n🔗 Links:\n" +
            "\n".join(f"- {url}" for url in urls[:3])
        )
    
    return f"**Info:** {answer}\n\n🔗 Links:\n" + "\n".join(f"- {url}" for url in urls[:3])


