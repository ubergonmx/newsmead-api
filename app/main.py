from fastapi import FastAPI, Request, HTTPException
from collections import defaultdict
from app.api import articles, base, logviewer, recommender
import logging.config
import random
import string
import time
import app.backend.config as config


# Configure logging
log = logging.getLogger(__name__)

# Configure app
app = FastAPI(lifespan=config.lifespan)
app.include_router(base.router)
app.include_router(articles.router, prefix="/articles")
app.include_router(recommender.router, prefix="/recommender")
app.include_router(logviewer.router, prefix="/logviewer")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    idem = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    ip = request.client.host
    log.info(f"rid={idem} start request path={request.url.path} ip={ip}")
    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    log.info(
        f"rid={idem} completed_in={formatted_process_time}ms status_code={response.status_code} ip={ip}"
    )

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)

# Store the timestamp of the last request from each IP
last_request = defaultdict(int)
# Store the number of requests from each IP in the last second
request_counts = defaultdict(int)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = request.client.host

    # If the IP is blocked, return a 429 response
    if time() - last_request[ip] < 1 and request_counts[ip] > 10:
        raise HTTPException(status_code=429, detail="Too Many Requests")

    # Update the timestamp of the last request and the request count
    if time() - last_request[ip] > 1:
        last_request[ip] = time()
        request_counts[ip] = 1
    else:
        request_counts[ip] += 1

    response = await call_next(request)
    return response
