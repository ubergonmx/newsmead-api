# NewsMead API

A news recommender API built with FastAPI for the NewsMead mobile app.

## Tech Stack

- Python/FastAPI

## API Endpoints

API URL: _not yet available_

List of **GET** endpoints:

- _currently in development_

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

2. Setup Playwright

```bash
playwright install
```

3. Add recommender system

```bash
cd app/core
python setup.py
```

4. Run server

```bash
# go back to project root folder
cd ../..

uvicorn app.main:app --reload
# or
python -m app.main
```
