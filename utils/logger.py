# ============================================================
# NEXUS PRO - Logger
# ============================================================
# Merkezi loglama yapılandırması
# ============================================================

import logging
import sys
from datetime import datetime
from pathlib import Path

def setup_logger(
    name: str = "nexus_pro",
    level: str = "INFO",
    log_file: bool = True
) -> logging.Logger:
    """
    Logger yapılandır
    
    Args:
        name: Logger adı
        level: Log seviyesi
        log_file: Dosyaya da yaz
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        today = datetime.now().strftime("%Y%m%d")
        file_handler = logging.FileHandler(
            logs_dir / f"nexus_pro_{today}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
        
    return logger


def get_logger(name: str) -> logging.Logger:
    """Alt logger al"""
    return logging.getLogger(f"nexus_pro.{name}")
