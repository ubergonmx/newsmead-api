from fastapi import FastAPI, Request
from app.api import base, logviewer, recommender
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
app.include_router(logviewer.router, prefix="/logviewer")
app.include_router(recommender.router, prefix="/recommender")


# API endpoints
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
