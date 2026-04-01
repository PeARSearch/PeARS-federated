# SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os import getenv

def run_logging():
    log_level = getenv('LOG_LEVEL', 'INFO').upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    logging.basicConfig(level=numeric_level, filename="system.log",
                        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
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
        handler.setFormatter(formatter)
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        return logger

    mail_logger = setup_logger('mailing_logger', 'mailing.log', level=logging.MAILING)
    mail_logger.mailing("Mailing logging initialized.")
    return mail_logger
