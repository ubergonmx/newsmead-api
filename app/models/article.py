from pydantic import BaseModel, Field


class Article(BaseModel):
    date: str = ""
    category: str
    source: str
    title: str
    author: str = ""
    url: str
    body: str = ""
    image_url: str = ""
    read_time: str = ""
