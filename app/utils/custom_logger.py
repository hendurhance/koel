import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime
import slack_sdk
import threading
from functools import lru_cache
from pathlib import Path

class CustomLogger:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure one logger instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CustomLogger, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        app_name: str = "app",
        log_level: str = "INFO",
        log_dir: str = "logs",
        log_file_name: str = "app.log",
        slack_webhook: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        if self._initialized:
            return

        self.app_name = app_name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_dir = Path(log_dir)
        self.log_file_name = log_file_name
        self.slack_webhook = slack_webhook
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.slack_client = slack_sdk.WebClient() if slack_webhook else None

        # Create logs directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize logger
        self.logger = logging.getLogger(self.app_name)
        self.logger.setLevel(self.log_level)

        # Clear any existing handlers
        self.logger.handlers = []

        # Setup handlers
        self._setup_console_handler()
        self._setup_file_handler()
        if self.slack_webhook:
            self._setup_slack_handler()

        self._initialized = True

    def _setup_console_handler(self):
        """Configure console output with colored formatting."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        
        class ColoredFormatter(logging.Formatter):
            COLORS = {
                'DEBUG': '\033[94m',    # Blue
                'INFO': '\033[92m',     # Green
                'WARNING': '\033[93m',  # Yellow
                'ERROR': '\033[91m',    # Red
                'CRITICAL': '\033[95m', # Magenta
                'RESET': '\033[0m'
            }

            def format(self, record):
                level = record.levelname
                color = self.COLORS.get(level, '')
                message = super().format(record)
                return f"{color}{message}{self.COLORS['RESET']}"

        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def _setup_file_handler(self):
        """Configure rotating file handler with a single fixed log file."""
        log_file = self.log_dir / self.log_file_name
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count
        )
        file_handler.setLevel(self.log_level)
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def _setup_slack_handler(self):
        """Configure Slack handler for ERROR and CRITICAL logs."""
        class SlackHandler(logging.Handler):
            def __init__(self, logger_instance):
                super().__init__()
                self.logger_instance = logger_instance
                self.setLevel(logging.ERROR)

            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.logger_instance._send_to_slack({
                        "text": f"*{record.levelname}* in *{self.logger_instance.app_name}*\n"
                                f"```{msg}```\n"
                                f"File: {record.filename}:{record.lineno}"
                    })
                except Exception as e:
                    print(f"Failed to send Slack message: {e}")

        slack_handler = SlackHandler(self)
        slack_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        slack_handler.setFormatter(slack_formatter)
        self.logger.addHandler(slack_handler)

    @lru_cache(maxsize=100)
    def _send_to_slack(self, message: dict):
        """Send message to Slack with caching to prevent duplicate messages."""
        if self.slack_client:
            try:
                self.slack_client.chat_postMessage(
                    channel="#logs",
                    **message
                )
            except Exception as e:
                print(f"Slack notification failed: {e}")

    def __getattr__(self, name):
        """
        Delegate logging methods (debug, info, warning, error, critical, exception) to the underlying logger.
        This ensures the caller's file and line number are captured correctly.
        """
        return getattr(self.logger, name)


def get_logger(
    app_name: str = "app",
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_file_name: str = "app.log",
    slack_webhook: Optional[str] = None
) -> CustomLogger:
    """Factory function to get or create a logger instance."""
    return CustomLogger(
        app_name=app_name,
        log_level=log_level,
        log_dir=log_dir,
        log_file_name=log_file_name,
        slack_webhook=slack_webhook
    )