import logging
from os import makedirs, path
from datetime import datetime

def setup_logger(logger_name, level=logging.DEBUG):
    logs_dir = 'logs'
    makedirs(logs_dir, exist_ok=True)
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
	# Prevent duplicate handlers if called multiple times.
    '''
    Note logger object canh have multiple handler and each handler can have different file,
    But for simplicity here we use single handler.
    '''
    if not logger.handlers:
        log_file=datetime.now().strftime(f'{logger_name}_%Y%m%d.log')
        fh = logging.FileHandler(path.join(logs_dir, log_file))
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s] - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger

