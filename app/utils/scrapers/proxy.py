# Copyright (c) ubergonmx. All rights reserved.
# Licensed under the BSD 2-Clause License.

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import logging
import json

# Configure logging
log = logging.getLogger(__name__)


class ProxyScraper:
    def __init__(self, scrape_proxy_init=True):
        self.current_proxy_index = 0
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--ignore-certificate-errors")
        self.chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:39.0) Gecko/20100101 Firefox/39.0"
        )
        self.chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-logging"]
        )

        if scrape_proxy_init:
            self.proxies = self.scrape_proxies()

    def get_next_proxy(self) -> dict[str, str]:
        if self.proxies is None or len(self.proxies) == 0:
            return None
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return {"http://": proxy} if proxy.startswith("http:") else {"https://": proxy}

    def scrape_url(self, url: str) -> str:
        driver = webdriver.Chrome(options=self.chrome_options)
        driver.get(url)
        time.sleep(5)
        html_content = driver.page_source
        driver.quit()
        return html_content

    def scrape_proxies(self) -> list[str]:
        driver = webdriver.Chrome(options=self.chrome_options)
        # Proxy provider: SPYS.one
        spys_url = "https://spys.one/free-proxy-list/PH/"
        driver.get(spys_url)

        # Wait for the page to load (adjust the sleep time if needed)
        time.sleep(5)

        # Extract the HTML content after the page has loaded
        html_content = driver.page_source

        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract proxies from the page as before
        proxies = []

        # Find the 3rd table
        proxy_table = soup.find_all("table")[2]

        # Get tbody in table
        tbody = proxy_table.find("tbody")

        # Get all rows with onmouseover property
        rows = tbody.find_all("tr", {"onmouseover": "this.style.background='#002424'"})

        for row in rows:
            columns = row.find_all("td")
            ip = columns[0].text.strip()
            proxy_type = columns[1].text.strip().split(" ")[0].lower()
            proxy = f"{proxy_type}://{ip}"
            proxies.append(proxy)

        # Close the browser window
        driver.quit()

        # Remove "socks" proxies
        proxies = [proxy for proxy in proxies if "socks" not in proxy]
        log.info(f"Scraped {len(proxies)} proxies: {json.dumps(proxies, indent=2)}")
        return proxies

    def refresh_proxies(self):
        log.info("Refreshing proxies...")
        self.proxies = self.scrape_proxies()
        self.current_proxy_index = 0

    def get_proxies(self):
        return self.proxies
