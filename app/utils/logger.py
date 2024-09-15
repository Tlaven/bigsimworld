import logging
import os

from logging.handlers import RotatingFileHandler

def setup_logger(log_file: str = 'logs/app.log', level: int = logging.INFO):
    """
    配置带日志轮换功能的日志记录器
    """
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    if not logger.hasHandlers():
        # 使用 RotatingFileHandler 实现日志轮换
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
        file_handler.setLevel(level)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    return logger

