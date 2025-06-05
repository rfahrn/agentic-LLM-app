import os
import re
from langchain.tools import Tool
from tavily import TavilyClient

# Load Tavily API key
#api_key = os.getenv("TAVILY_API_KEY")
try:
    import streamlit as st
    api_key = st.secrets["TAVILY"]["TAVILY_API_KEY"]
except Exception:
    pass

client = TavilyClient(api_key=api_key)

def label_type(url: str) -> str:
    if "/mpro" in url:
        return "📄 Fachinformation"
    elif "/mpub" in url:
        return "👥 Patienteninformation"
    elif "/product" in url:
        return "📦 Produktinformation"
    return "🔗 Link"

def get_compendium_info(prompt: str) -> str:
    """Find product link via Tavily. Then show that as main output with guidance."""
    query = f"site:compendium.ch/product {prompt}"
    try:
        results = client.search(query=query, search_depth="advanced", include_answer=False)
        urls = [r.get("url") for r in results.get("results", []) if r.get("url")]
        product_link = next((u for u in urls if "compendium.ch/product/" in u), None)

        if not product_link:
            return "⚠️ Keine passende Produktseite gefunden."

        # Add specific subpages
        output = [f"### 🔗 Produkt gefunden:\n- [Produktseite]({product_link})"]
        for suffix, label in [("/mpro", "Fachinformation"), ("/mpub", "Patienteninformation")]:
            output.append(f"- [{label}]({product_link}{suffix})")

            st.markdown(f"""
            🔍 **Gefundene Seite:**  
            - [Produktseite]({product_link})  
            - [Fachinformation]({product_link}/mpro)  
            - [Patienteninformation]({product_link}/mpub)
            """)
        return "\n".join(output)

    except Exception as e:
        return f"❌ Fehler bei Tavily-Suche: {e}"

def get_product_url_only(prompt: str) -> str:
    query = f"site:compendium.ch/product {prompt}"
    try:
        results = client.search(query=query, include_answer=False)
        urls = [r["url"] for r in results.get("results", []) if r.get("url")]
        return next((u for u in urls if re.match(r"https://compendium\.ch/product/\d+-", u)), None)
    except Exception:
        return None
    
# LangChain tool definition
CompendiumTavilyTool = Tool(
    name="Compendium.ch (Tavily)",
    func=get_compendium_info,
    description=(
        "Ruft gezielt Fachinformation, Patienteninfo und Produktbeschreibung von Compendium.ch ab. "
        "Nur bei echten Medikamententreffern wird Inhalt extrahiert."
    ),
)
