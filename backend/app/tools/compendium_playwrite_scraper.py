# backend/app/tools/compendium_playwright_scraper.py


from playwright.sync_api import sync_playwright


# backend/app/tools/compendium_playwright_scraper.py

from playwright.sync_api import sync_playwright

def scrape_compendium_pages(base_url: str) -> tuple[str, list[str]]:
    variants = [base_url, f"{base_url}/mpro", f"{base_url}/mpub", f"{base_url}/product"]
    collected = []
    used_urls = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for url in variants:
                page.goto(url, timeout=20000)
                page.wait_for_timeout(3000)
                try:
                    text = page.inner_text("body")
                    if text:
                        label = url.split("/")[-1] or "Produkt"
                        collected.append(f"### {label}\n📎 {url}\n\n{text[:8000]}...")
                        used_urls.append(url)
                except Exception:
                    continue

            browser.close()

        return ("\n\n---\n\n".join(collected), used_urls) if collected else ("", [])

    except Exception as e:
        return (f"❌ Fehler beim Scraping: {e}", [])

    
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# backend/app/tools/llm_answer_tool.py

from langchain_openai import ChatOpenAI 
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

def summarize_compendium_with_llm(scraped_text: str, user_question: str, source_urls: list[str]) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=False)

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""
            Du bist ein pharmazeutischer Assistent.

            Nutze den folgenden Auszug von Compendium.ch, um die Frage knapp und verständlich zu beantworten.
            Antworte ausschließlich auf Deutsch.

            ===
            {context}
            ===

            Frage: {question}
            Antworte präzise in maximal 4 Sätzen. Falls du keine Antwort findest, sage "Keine Antwort gefunden".
            """
    )

    chain = LLMChain(llm=llm, prompt=prompt)
    answer = chain.run(context=scraped_text, question=user_question)

    if source_urls:
        link = source_urls[0]
        return f"{answer.strip()}\n\n🔗 [Quelle auf Compendium.ch]({link})"
    else:
        return f"{answer.strip()}\n\n⚠️ Keine Quelle gefunden."

