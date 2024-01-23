# NewsMead API

A news recommender API built with FastAPI for the NewsMead mobile app.

## Tech Stack

- Python/FastAPI

## API Endpoints

API URL: _not yet available_

List of **GET** endpoints:

- `/search?q=[query]` - returns articles searched with the query and scraped from Google News
- `/parse?url=[url]` - returns scraped content of the article from the given url

## How to run

> **NOTE**: Must have Python version **3.9** for recommenders package.
>
> (Optional)
> Install and use virtual environment with `virtualenv`
>
> ```bash
> pip install virtualenv
> virtualenv -p python3.9 venv
> "./venv/Scripts/activate"
> ```

1. Install requirements

```bash
pip install -r requirements.txt
```

2. Run server

```bash
uvicorn app.main:app --reload
# or
python -m app.main
```
