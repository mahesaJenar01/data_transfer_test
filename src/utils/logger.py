import logging

def setup_logger(logger_name: str, level: str= 'INFO'):
    """
    Set up a logger with specified level.
    
    Args:
        logger_name: Name for the logger instance
        level: Logging level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Convert string level to logging constant if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    
    # Create logger with caller's name
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Create console handler and set level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add formatter to handler
    console_handler.setFormatter(formatter)
    
    # Add handler to logger if it doesn't already have handlers
    if not logger.handlers:
        logger.addHandler(console_handler)
    
    return logger