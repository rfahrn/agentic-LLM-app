# compendium_tool.py
# tools/compendium_scraper_tool.py
import os, re, requests
from bs4 import BeautifulSoup
from langchain.tools import Tool

LOGIN_URL = "https://compendium.ch/account/login"

def get_logged_in_session():
    session = requests.Session()
    username = os.getenv("HCI_USERNAME")
    password = os.getenv("HCI_PASSWORD")
    res = session.get(LOGIN_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    token = soup.find("input", {"name": "__RequestVerificationToken"})
    csrf = token["value"] if token else None

    payload = {
        "__RequestVerificationToken": csrf,
        "Email": username,
        "Password": password
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    login_resp = session.post(LOGIN_URL, data=payload, headers=headers)
    if "abmelden" not in login_resp.text.lower():
        raise Exception("Login failed")
    return session

def scrape_page(session, url):
    res = session.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    content = soup.find("div", class_="product-detail-content")
    return content.get_text("\n", strip=True)[:2000] if content else "❌ Kein lesbarer Inhalt gefunden."

def compendium_scraper_func(url: str) -> str:
    try:
        session = get_logged_in_session()
        base = scrape_page(session, url)
        fach = scrape_page(session, f"{url}/mpro")
        patient = scrape_page(session, f"{url}/mpub")
        return f"""
📦 **Produktseite**: {url}

{base}

📄 **Fachinformation**:
{fach}

👥 **Patienteninformation**:
{patient}
"""
    except Exception as e:
        return f"❌ Fehler beim Scraper: {str(e)}"

compendium_scraper_tool = Tool(
    name="compendium_scraper",
    func=compendium_scraper_func,
    description="Scrapes detailed pharma information from compendium.ch URLs. Requires full product URL."
)

