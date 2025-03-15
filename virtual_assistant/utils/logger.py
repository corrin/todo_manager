import logging
import os
import sys

# Create the logger instance
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a file handler
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.log")
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Create a console handler with proper encoding for Windows
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(logging.DEBUG)

# Create a formatter with filename and line number
formatter = logging.Formatter("%(asctime)s %(levelname)s [%(filename)s:%(lineno)d]: %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Disable propagation to avoid duplicate logs
logger.propagate = False

# Configure exception logging - disable full traceback logging
logging.getLogger().setLevel(logging.ERROR)

# Explicitly disable exception traceback reporting when logging errors
def exception_handler(exc_type, exc_value, exc_traceback):
    """Custom exception handler to avoid printing traceback"""
    logger.error(f"Uncaught exception: {exc_value}", exc_info=False)

# Set up the exception handler for uncaught exceptions
sys.excepthook = exception_handler
