# backend/app/tools/compendium_playwright_scraper.py


from playwright.sync_api import sync_playwright

def scrape_compendium_pages(base_url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(base_url, timeout=15000)
            page.wait_for_timeout(3000)  # wait for JavaScript rendering

            content = page.content()
            text = page.inner_text("body")

            browser.close()
            return text[:1500] + "..." if text else "⚠️ Keine lesbaren Inhalte gefunden."

    except Exception as e:
        return f"❌ Fehler beim Scraping: {e}"

