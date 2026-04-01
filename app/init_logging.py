# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv


class ColorFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes for terminal output."""

    COLORS = {
        logging.DEBUG:    '\033[36m',   # cyan
        logging.INFO:     '\033[32m',   # green
        logging.WARNING:  '\033[33m',   # yellow
        logging.ERROR:    '\033[31m',   # red
        logging.CRITICAL: '\033[1;31m', # bold red
    }
    RESET = '\033[0m'
    DIM = '\033[2m'

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        levelname = f"{color}{record.levelname:<8}{self.RESET}"
        name = f"{self.DIM}{record.name}{self.RESET}"
        timestamp = f"{self.DIM}{self.formatTime(record, self.datefmt)}{self.RESET}"
        msg = f"{timestamp} {levelname} {name} | {record.getMessage()}"
        if record.levelno <= logging.DEBUG:
            location = f"{self.DIM}{record.pathname}:{record.lineno}{self.RESET}"
            msg = f"{timestamp} {levelname} {name} {location} | {record.getMessage()}"
        return msg


def run_logging():
    log_level = getenv('LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    # File handler — plain text, no color codes
    if numeric_level <= logging.DEBUG:
        file_fmt = '%(asctime)s | %(levelname)s | %(name)s | %(pathname)s:%(lineno)d | %(message)s'
    else:
        file_fmt = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    file_formatter = logging.Formatter(file_fmt)
    file_handler = logging.FileHandler("system.log")
    file_handler.setFormatter(file_formatter)

    # Console handler — colored output
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.info("System logging initialized at level %s.", log_level)

    # Custom log level for mailing
    MAILING = 55
    logging.MAILING = MAILING
    logging.addLevelName(logging.MAILING, 'MAILING')

    def mailing(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.MAILING):
            self._log(logging.MAILING, message, args, **kwargs)

    logging.Logger.mailing = mailing

    def setup_logger(name, log_file, level=logging.INFO):
        handler = logging.FileHandler(log_file)
        handler.setFormatter(file_formatter)
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        return logger

    mail_logger = setup_logger('mailing_logger', 'mailing.log', level=logging.MAILING)
    mail_logger.mailing("Mailing logging initialized.")
    return mail_logger
