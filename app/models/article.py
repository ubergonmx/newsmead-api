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
    image_url: Optional[str] = ""
    read_time: str = ""


class Filter(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    sortBy: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
