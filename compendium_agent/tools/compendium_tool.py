import re
import requests
from bs4 import BeautifulSoup
from langchain.tools import Tool
from .tavily_tool_ import TavilyTool
import requests, re
from bs4 import BeautifulSoup
from tools.tavily_tool_ import tavily_tool

# compendium_agent/tools/compendium_tool.py

import requests, re
from bs4 import BeautifulSoup

def extract_compendium_links(results):
    product_url = fachinfo_url = patientinfo_url = None
    for r in results:
        url = r.get("url", "")
        title = r.get("title", "").lower()
        if not url.startswith("https://compendium.ch"):
            continue
        if re.search(r"/product/\d+-", url):
            if "dolo" in title or "tabl" in title or "500 mg" in title:
                product_url = url if not product_url else product_url
        if "/mpro" in url:
            fachinfo_url = url
        if "/mpub" in url:
            patientinfo_url = url
    return {
        "Produktseite": product_url,
        "Fachinformation": fachinfo_url,
        "Patienteninformation": patientinfo_url,
    }

def scrape_compendium_product_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        content_div = soup.find("div", class_="productDetail")
        if not content_div:
            return "⚠️ Kein relevanter Inhalt gefunden."
        text_blocks = [
            p.get_text(separator=" ", strip=True)
            for p in content_div.find_all(["h1", "h2", "p", "li"])
        ]
        filtered = "\n".join([line for line in text_blocks if line and not line.startswith("Drucken")])
        return filtered[:5000] + "..."
    except Exception as e:
        return f"❌ Fehler beim Abrufen von Compendium-Seite: {e}"

# Public lookup function
def get_compendium_info_with_scraping(prompt, tavily_tool):
    query = f"site:compendium.ch {prompt}"
    try:
        results = tavily_tool.run(query)
        links = extract_compendium_links(results)
        if not links["Produktseite"]:
            return f"⚠️ Kein Produktlink gefunden für {prompt}."
        summary = scrape_compendium_product_page(links["Produktseite"])
        return f"### 📦 Informationen zu **{prompt}**\n\n{summary}\n\n🔗 [Produktlink]({links['Produktseite']})"
    except Exception as e:
        return f"❌ Fehler bei Tavily- oder Scrape-Suche: {e}"
