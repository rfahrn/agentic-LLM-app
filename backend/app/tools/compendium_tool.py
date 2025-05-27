#!/usr/bin/env python3
# tools/compendium_tool.py

import os
import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typing import List, Dict
from streamlit import st

load_dotenv()

HCI_USERNAME = os.getenv("HCI_USERNAME")
#HCI_USERNAME = st.secrets.HCI.HCI_USERNAME

HCI_PASSWORD = os.getenv("HCI_PASSWORD")
#HCI_PASSWORD = st.secrets.HCI.HCI_PASSWORD
HCI_URL = "https://index.hcisolutions.ch/Index/current/get.aspx"

def fetch_compendium_xml(drug_name: str) -> ET.Element:
    """Fetches and parses the Compendium.ch XML data for the given drug name."""
    params = {
        "schema": "COMPENDIUM",
        "keytype": "NAME",
        "key": drug_name,
        "index": "hospINDEX",
        "xsl": "prettyxml.xslt",
    }
    resp = requests.get(HCI_URL, params=params, auth=(HCI_USERNAME, HCI_PASSWORD))
    resp.raise_for_status()
    return ET.fromstring(resp.content)

def extract_relevant_sections(root: ET.Element, ns: Dict[str, str], query: str) -> List[Dict]:
    """Parses and filters the document for sections relevant to the query."""
    results = []
    for cp in root.findall("ns:CP", ns):
        if cp.attrib.get("LANG") != "DE":
            continue

        product_name = BeautifulSoup(cp.find("ns:NAME", ns).text or "", "html.parser").get_text(strip=True)
        content_html = cp.find("ns:CONTENT", ns).text or ""

        if "<div" not in content_html:
            continue

        soup = BeautifulSoup(content_html, "html.parser")
        for sec in soup.select("div.paragraph"):
            h2 = sec.find(re.compile(r"^h[2]$"))
            if not h2:
                continue
            section_title = h2.get_text(strip=True)
            section_text = sec.get_text(" ", strip=True)

            if query.lower() in section_text.lower() or query.lower() in section_title.lower():
                chunks = extract_section_chunks(sec)
                results.append({
                    "product": product_name,
                    "section_title": section_title,
                    "text": "\n\n".join(chunks),
                    "source": f"https://compendium.ch/product/{product_name.replace(' ', '%20')}"
                })

    return results

def extract_section_chunks(sec) -> List[str]:
    """Extracts formatted chunks (paragraphs, lists, tables) from a <div.paragraph> section."""
    chunks = []
    for node in sec.children:
        name = getattr(node, "name", None)
        if name == "h2":
            continue
        if name == "p":
            text = node.get_text(" ", strip=True)
            if text:
                chunks.append(text)
        elif name in ("ul", "ol"):
            for li in node.find_all("li"):
                text = li.get_text(" ", strip=True)
                if text:
                    chunks.append("• " + text)
        elif name == "table":
            rows = []
            for tr in node.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(cells)
            if rows:
                header, *body = rows
                md = ["| " + " | ".join(header) + " |",
                      "| " + " | ".join("---" for _ in header) + " |"]
                for row in body:
                    md.append("| " + " | ".join(row) + " |")
                chunks.append("\n".join(md))
    return chunks

def save_results(results: List[Dict], output_dir: str, base_name: str):
    """Saves the extracted results to disk as markdown and JSON (for embedding)."""
    import json

    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, f"{base_name}.md")
    json_path = os.path.join(output_dir, f"{base_name}.json")

    with open(md_path, "w", encoding="utf-8") as f_md:
        for r in results:
            f_md.write(f"# {r['product']}\n")
            f_md.write(f"## {r['section_title']}\n")
            f_md.write(r['text'] + "\n\n---\n\n")

    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(results, f_json, ensure_ascii=False, indent=2)

    print(f"✅ Markdown saved to {md_path}")
    print(f"✅ JSON for embeddings saved to {json_path}")

def extract_and_save(query: str, drug_name: str, output_dir: str = r"C:\Users\FahRe\Desktop\agentic-LLM-app\backend\data\Compendium_database"):
    """Main utility function to run the tool pipeline."""
    ns = {"ns": "http://www.hcisolutions.ch/index"}
    print(f"🔍 Fetching data for {drug_name}...")
    root = fetch_compendium_xml(drug_name)
    print(f"🔎 Extracting sections matching query: '{query}'...")
    results = extract_relevant_sections(root, ns, query)
    base_name = f"{drug_name.lower().replace(' ', '_')}_{query.lower().replace(' ', '_')}"
    save_results(results, output_dir, base_name)
    return results
