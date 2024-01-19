# Create a log viewer for the log file
# This will display HTML in a web browser
# The log file is a text file containing ASCII escape sequences
# to control the color of the text

import os
import sys
import time

# Get the log file name from the command line
if len(sys.argv) < 2:
    print("Usage: logviewer.py <logfile>")
    sys.exit(1)

# Get the log file name
logfile = sys.argv[1]

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
