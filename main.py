from fastapi import FastAPI
from proxyscrape import scrape_proxies

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/proxies")
def get_proxies():
    proxies = scrape_proxies()
    return {"proxies": proxies}
