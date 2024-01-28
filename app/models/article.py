from typing import Optional
from pydantic import BaseModel


class Article(BaseModel):
    article_id: Optional[int] = None
    date: str = ""
    category: str
    source: str
    title: str
    author: str = ""
    url: str
    body: str = ""
    image_url: str = ""
    read_time: str = ""
