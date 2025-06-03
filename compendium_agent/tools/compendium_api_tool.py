# tools/compendium_api_tool.py
import os, re, requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from langchain.tools import Tool

def get_api_info(product_name: str) -> str:
    username = os.getenv("HCI_USERNAME")
    password = os.getenv("HCI_PASSWORD")
    url = "https://index.hcisolutions.ch/Index/current/get.aspx"
    params = {
        "schema": "COMPENDIUM",
        "keytype": "NAME",
        "key": product_name,
        "index": "hospINDEX",
        "xsl": "prettyxml.xslt",
    }

    res = requests.get(url, params=params, auth=(username, password))
    res.raise_for_status()
    root = ET.fromstring(res.content)
    ns = {"ns": "http://www.hcisolutions.ch/index"}

    text_parts = []
    for cp in root.findall("ns:CP", ns):
        if cp.attrib.get("LANG") != "DE":
            continue
        content = cp.find("ns:CONTENT", ns)
        if content is not None and "<div" in (content.text or ""):
            soup = BeautifulSoup(content.text, "html.parser")
            for div in soup.select("div.paragraph"):
                h2 = div.find("h2")
                if h2:
                    text_parts.append("## " + h2.get_text(strip=True))
                ps = div.find_all(["p", "li"])
                for p in ps:
                    text_parts.append(p.get_text(strip=True))

    return "\n".join(text_parts[:2000]) if text_parts else "❌ Keine lesbaren Inhalte gefunden."

compendium_api_tool = Tool(
    name="compendium_api",
    func=get_api_info,
    description="Retrieves pharma information via the official Compendium XML API. Input must be a drug name (e.g. Dafalgan)."
)
