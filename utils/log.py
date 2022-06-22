import logging


# setup function to create the log file
def setup(log_filename):
    logging.basicConfig(filename=log_filename, filemode='w', format='%(asctime)s %(message)s', level=logging.DEBUG)
    logger = logging.getLogger("Debug")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(filename=log_filename)
    fh.setLevel(logging.DEBUG)
    # TODO add another handler and add to another level
    logger.addHandler(fh)
    return logger
