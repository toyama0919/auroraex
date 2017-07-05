import logging
from logging import getLogger, StreamHandler, INFO, DEBUG

def get_logger(debug):
    log_fmt = '%(asctime)s- %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=log_fmt)

    logger = getLogger(__name__)
    if debug:
        logger.setLevel(DEBUG)
    else:
        logger.setLevel(INFO)
    return logger
