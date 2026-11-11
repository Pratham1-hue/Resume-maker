from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from typing import Optional


class PortfolioScraper:
    """Portfolio scraper: httpx + BeautifulSoup first, Playwright fallback.

    v1 returns whatever readable text httpx extracts (even short pages) so a
    thin portfolio still contributes evidence instead of being dropped.
    Playwright is used only when httpx yields nothing useful.
    """

    def __init__(self, http_client: httpx.AsyncClient, threshold: int = 200):
        self.http = http_client
        self.threshold = threshold  # below this length we *prefer* Playwright

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch portfolio page text content.

        Strategy: fast httpx path first; if it yields nothing (or only a
        thin shell, typical of JS-rendered pages), render with headless
        Chromium. A thin httpx result is kept as a last resort so nothing
        useful is ever dropped. Failures raise with the reason so ingest
        warnings say what actually went wrong.
        """
        thin: Optional[str] = None
        try:
            text = await self._fetch_with_httpx_bs4(url)
        except Exception:
            text = None

        if text and len(text.strip()) >= self.threshold:
            return text
        if text and text.strip():
            thin = text

        try:
            rendered = await self._fetch_with_playwright(url)
        except Exception as exc:
            if thin:
                return thin
            raise
        if rendered and rendered.strip():
            return rendered
        if thin:
            return thin
        return None

    async def _fetch_with_httpx_bs4(self, url: str) -> Optional[str]:
        """Fetch and extract text using httpx + BeautifulSoup."""
        resp = await self.http.get(url, timeout=30.0, follow_redirects=True)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script, style, nav, footer elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.decompose()

        main = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
        if main:
            text = main.get_text(separator=" ", strip=True)
        else:
            text = soup.body.get_text(separator=" ", strip=True) if soup.body else ""

        text = " ".join(text.split())
        return text if text else None

    async def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """Render JS-heavy pages with headless Chromium.

        Uses the *sync* Playwright driver inside a worker thread: the async
        driver's subprocess transport raises NotImplementedError on Windows
        under some event loops (uvicorn included). Returns None only when
        Playwright/the browser is not installed; anything else raises.
        """
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed; JS-rendered pages cannot be scraped. "
                "Install it with `pip install playwright` and run `playwright install chromium`."
            )
        import asyncio

        text = await asyncio.to_thread(self._render_with_playwright_sync, url)
        text = " ".join((text or "").split())
        return text if text else None

    @staticmethod
    def _render_with_playwright_sync(url: str) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()
                try:
                    page.goto(url, wait_until="networkidle", timeout=45000)
                except Exception:
                    # networkidle often never fires on polling pages.
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(2500)
                try:
                    page.evaluate("""async () => {
                        await new Promise((resolve) => {
                            let y = 0;
                            const step = () => {
                                y += Math.max(400, window.innerHeight * 0.8);
                                window.scrollTo(0, y);
                                if (y < document.body.scrollHeight) setTimeout(step, 250);
                                else resolve();
                            };
                            step();
                        });
                        window.scrollTo(0, 0);
                    }""")
                except Exception:
                    pass
                page.wait_for_timeout(1200)
                return page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            finally:
                browser.close()
