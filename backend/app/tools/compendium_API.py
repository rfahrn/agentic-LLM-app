from bs4 import BeautifulSoup
import requests
import xml.etree.ElementTree as ET
import os

HCI_USERNAME = os.getenv("HCI_USERNAME")
HCI_PASSWORD = os.getenv("HCI_PASSWORD")
url = "https://index.hcisolutions.ch/Index/current/get.aspx"

params = {"schema": "COMPENDIUM",
    "keytype": "NAME",
    "key": "Dafalgan",
    "index": "hospINDEX",
    "xsl": "prettyxml.xslt",
    }
response = requests.get(url, params=params, auth=(HCI_USERNAME, HCI_PASSWORD))

if response.status_code == 200:
    root = ET.fromstring(response.content)
    ns = {"ns": "http://www.hcisolutions.ch/index"}

    for cp in root.findall("ns:CP", ns):
        if cp.attrib.get("LANG", "") != "DE":
            continue

        name_html = cp.find("ns:NAME", ns)
        content_el = cp.find("ns:CONTENT", ns)

        if name_html is None or content_el is None:
            continue

        raw_html = content_el.text
        if not raw_html or "<div" not in raw_html:
            continue

        name = BeautifulSoup(name_html.text, "html.parser").get_text()
        soup = BeautifulSoup(raw_html, "html.parser")
        print(soup.prettify())
        #print(f"\n📦 **Product Name**: {name}")
        #print("=" * 80)
        #print("📜 **Content**:\n" + "=" * 80)

        for section in soup.select("div.paragraph"):
            for tag in section.descendants:
                if tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    level = "🔹" if tag.name in ["h1", "h2"] else "🔸"
                    #print(f"\n{level} {tag.get_text(strip=True)}")

                elif tag.name == "li":
                    # Preserve bold text in <strong>
                    bold = tag.find("strong")
                    if bold:
                        bold_text = bold.get_text(strip=True)
                        rest = tag.get_text(strip=True).replace(bold_text, "", 1)
                        #print(f"• **{bold_text}**{rest}")
                    else:
                        #print(f"• {tag.get_text(strip=True)}")
                        pass

                elif tag.name == "p":
                    text = tag.get_text(strip=True)
                    if text:
                        #print(f"• {text}")
                        pass
    print("=" * 80)
else:
    print("❌ Error:", response.text)