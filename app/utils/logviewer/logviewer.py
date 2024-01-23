# Create a log viewer for the log file
# This will display HTML in a web browser
# The log file is a text file containing ASCII escape sequences
# to control the color of the text

import os
import sys
import time

# import fastapi and set router
from fastapi import APIRouter

router = APIRouter()

# import templates
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

# import request
from fastapi import Request

# import response
from fastapi.responses import HTMLResponse

# import log file
from fastapi import File
from fastapi import UploadFile

# import static files
from fastapi.staticfiles import StaticFiles

# add route for static files
router.mount("/static", StaticFiles(directory="static"), name="static")


# add route for index.html
@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# add route for log file
@router.get("/log", response_class=HTMLResponse)
async def log(request: Request):
    return templates.TemplateResponse("log.html", {"request": request})


# get log file from /logviewer/[log file]
@router.get("/logviewer/{logfile}")
async def get_log(logfile: str):
    logfile = "logs/" + logfile

    # Check if the log file exists
    if not os.path.exists(logfile):
        print("Error: Log file '%s' not found" % logfile)
        sys.exit(1)

    # Open the log file
    try:
        f = open(logfile, "r")
    except Exception as e:
        print("Error: Failed to open log file '%s': %s" % (logfile, str(e)))
        sys.exit(1)

    # Read the log file
    try:
        log = f.read()
    except Exception as e:
        print("Error: Failed to read log file '%s': %s" % (logfile, str(e)))
        sys.exit(1)

    # Close the log file
    try:
        f.close()
    except Exception as e:
        print("Error: Failed to close log file '%s': %s" % (logfile, str(e)))
        sys.exit(1)

    # Convert the log file to HTML
    html = log.replace("\n", "<br>")
    html = html.replace("\x1b[0m", "</span>")
    html = html.replace("\x1b[1m", "<span style='font-weight:bold'>")
    html = html.replace("\x1b[2m", "<span style='opacity:0.5'>")
    html = html.replace("\x1b[31m", "<span style='color:red'>")
    html = html.replace("\x1b[32m", "<span style='color:green'>")
    html = html.replace("\x1b[33m", "<span style='color:yellow'>")
    html = html.replace("\x1b[34m", "<span style='color:blue'>")
    html = html.replace("\x1b[35m", "<span style='color:magenta'>")
    html = html.replace("\x1b[36m", "<span style='color:cyan'>")
    html = html.replace("\x1b[37m", "<span style='color:white'>")
    html = html.replace("\x1b[40m", "<span style='background-color:black'>")
    html = html.replace("\x1b[41m", "<span style='background-color:red'>")
    html = html.replace("\x1b[42m", "<span style='background-color:green'>")
    html = html.replace("\x1b[43m", "<span style='background-color:yellow'>")
    html = html.replace("\x1b[44m", "<span style='background-color:blue'>")
    html = html.replace("\x1b[45m", "<span style='background-color:magenta'>")
    html = html.replace("\x1b[46m", "<span style='background-color:cyan'>")
    html = html.replace("\x1b[47m", "<span style='background-color:white'>")

    # Display the log file in a web browser
    print("Displaying log file '%s' in a web browser" % logfile)
    return html
