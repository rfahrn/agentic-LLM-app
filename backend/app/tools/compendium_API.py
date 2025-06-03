#!/usr/bin/env python3
# tools/compendium_API.py --key Ozempic --output-dir .data\Compendium_database 

import os
import argparse
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
import json

def extract_section_tables(sec):
    """
    Given a <div.paragraph> element, walk its direct children and
    extract paragraphs, list items, and tables as markdown/text chunks.
    """
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
            # build markdown table
            rows = []
            for tr in node.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th","td"])]
                if cells:
                    rows.append(cells)
            if rows:
                header, *body = rows
                md = []
                # header row
                md.append("| " + " | ".join(header) + " |")
                # separator
                md.append("| " + " | ".join("---" for _ in header) + " |")
                # body rows
                for row in body:
                    md.append("| " + " | ".join(row) + " |")
                chunks.append("\n".join(md))
    return chunks

def fetch_and_parse(key):
    import streamlit as st
    """
    Fetches the XML for a given key from the HCIndex API and returns
    the parsed ElementTree root and namespace dict.
    """
    username = os.getenv("HCI_USERNAME")
    #username = st.secrets.HCI.HCI_USERNAME
    password = os.getenv("HCI_PASSWORD")
    #password = st.secrets.HCI.HCI_PASSWORD
    url = "https://index.hcisolutions.ch/Index/current/get.aspx"
    params = {
        "schema": "COMPENDIUM",
        "keytype": "NAME",
        "key": key,
        "index": "hospINDEX",
        "xsl": "prettyxml.xslt",
    }
    resp = requests.get(url, params=params, auth=(username, password))
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns = {"ns": "http://www.hcisolutions.ch/index"}
    return root, ns

def build_json(root, ns):
    products_json = {}
    for cp in root.findall("ns:CP", ns):
        if cp.attrib.get("LANG") != "DE":
            continue
        name_html = cp.find("ns:NAME", ns)
        product_name = BeautifulSoup(name_html.text or "", "html.parser").get_text(strip=True)
        products_json[product_name] = {"sections": {}}

        content_el = cp.find("ns:CONTENT", ns)
        raw_html = content_el.text or ""
        if "<div" not in raw_html:
            continue

        soup = BeautifulSoup(raw_html, "html.parser")
        for sec in soup.select("div.paragraph"):
            h2 = sec.find(re.compile(r"^h[2]$"))
            if not h2:
                continue
            section_title = h2.get_text(strip=True)
            section_chunks = extract_section_tables(sec)
            if section_chunks:
                products_json[product_name]["sections"][section_title] = "\n\n".join(section_chunks)

    return products_json

def build_markdown(root, ns):
    md_lines = []
    section_links = []
    for cp in root.findall("ns:CP", ns):
        if cp.attrib.get("LANG") != "DE":
            continue
        name_html = cp.find("ns:NAME", ns)
        product_name = BeautifulSoup(name_html.text or "", "html.parser").get_text(strip=True)
        md_lines.append(f"# {product_name}\n")

        content_el = cp.find("ns:CONTENT", ns)
        raw_html = content_el.text or ""
        if "<div" not in raw_html:
            continue

        soup = BeautifulSoup(raw_html, "html.parser")
        for sec in soup.select("div.paragraph"):
            h2 = sec.find(re.compile(r"^h[2]$"))
            if not h2:
                continue
            section_title = h2.get_text(strip=True)
            section_anchor = section_title.lower().replace(" ", "-").replace("/", "-")
            section_links.append((section_title, section_anchor))
            md_lines.append(f"## {section_title}\n")
            for chunk in extract_section_tables(sec):
                md_lines.append(chunk + "\n")
            md_lines.append("\n")

        md_lines.append("\n" + "="*40 + "\n")
    return "\n".join(md_lines), product_name, section_links




def main():
    parser = argparse.ArgumentParser(
        description="Extract HCIndex drug info into Markdown and TXT files."
    )
    parser.add_argument(
        "--key", required=True,
        help="Drug name (e.g. Ozempic)"
    )
    parser.add_argument(
        "--output-dir", default=".",
        help="Directory to save output files"
    )
    args = parser.parse_args()

    root, ns = fetch_and_parse(args.key)
    markdown, product_name, section_links = build_markdown(root, ns)
    json_data = build_json(root, ns)

    os.makedirs(args.output_dir, exist_ok=True)
    base_name = args.key.lower().replace(" ", "_")
    md_path = os.path.join(args.output_dir, f"{base_name}.md")
    txt_path = os.path.join(args.output_dir, f"{base_name}.txt")
    json_path = os.path.join(args.output_dir, f"{base_name}.json")

    with open(md_path, "w", encoding="utf-8") as f_md:
        f_md.write(markdown)
    with open(txt_path, "w", encoding="utf-8") as f_txt:
        f_txt.write(markdown)
    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(json_data, f_json, ensure_ascii=False, indent=4)

    print(f"Wrote Markdown to {md_path}")
    print(f"Wrote text to {txt_path}")
    print(f"Wrote JSON to {json_path}")

if __name__ == "__main__":
    main()