from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import logging
import json
import httpx

# Configure logging
log = logging.getLogger(__name__)


class ProxyScraper:
    def __init__(self):
        self.current_proxy_index = 0
        self.proxies = []

    async def scrape_url(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url)
                await page.wait_for_load_state(
                    "networkidle"
                )  # Ensure page is fully loaded
                html_content = await page.content()
                return html_content
            except Exception as e:
                log.error(f"Error scraping URL: {e}")
            finally:
                await browser.close()

    async def scrape_proxies(self) -> list[str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--ignore-certificate-errors",
                    f"--user-agent={UserAgent().chrome}",
                ],
            )
            page = await browser.new_page()
            try:
                await page.goto("https://spys.one/free-proxy-list/PH/")
                await page.wait_for_load_state("networkidle")
                html_content = await page.content()

                soup = BeautifulSoup(html_content, "html.parser")
                proxy_table = soup.find_all("table")[2]
                tbody = proxy_table.find("tbody")
                rows = tbody.find_all(
                    "tr", {"onmouseover": "this.style.background='#002424'"}
                )

                proxies = []
                for row in rows:
                    columns = row.find_all("td")
                    ip = columns[0].text.strip()
                    proxy_type = columns[1].text.strip().split(" ")[0].lower()
                    proxy = f"{proxy_type}://{ip}"
                    proxies.append(proxy)

                proxies = [proxy for proxy in proxies if "socks" not in proxy]
                log.info(
                    f"Scraped {len(proxies)} proxies: {json.dumps(proxies, indent=2)}"
                )
                self.proxies = proxies
            except Exception as e:
                log.error(f"Error scraping proxies: {e}")
            finally:
                await browser.close()

    def get_next_proxy(self) -> str:
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy

    def get_next_proxy_mounts(self) -> dict[str, str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        if proxy.startswith("http:"):
            return {"http://": httpx.HTTPTransport(proxy=proxy)}
        elif proxy.startswith("https:"):
            return {"https://": httpx.HTTPSTransport(proxy=proxy)}

    def get_proxies(self):
        return self.proxies
