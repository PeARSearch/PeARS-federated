import logging

def run_logging():
    # Set up basic logging configuration for the root logger
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    logging.basicConfig(level=logging.ERROR, filename="system.log", format='%(asctime)s | %(levelname)s : %(message)s')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.error("Checking system logs on init.")

    # Define a custom log level
    MAILING = 55
    logging.MAILING = MAILING
    logging.addLevelName(logging.MAILING, 'MAILING')

    # Define a custom logging method for the new level
    def mailing(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.MAILING):
            self._log(logging.MAILING, message, args, **kwargs)

    # Add the custom logging method to the logger class
    logging.Logger.mailing = mailing

    # Set up logger
    def setup_logger(name, log_file, level=logging.INFO):
        """To setup as many loggers as you want"""

        handler = logging.FileHandler(log_file)        
        handler.setFormatter(formatter)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)

        return logger

    mail_logger = setup_logger('mailing_logger', 'mailing.log', level=logging.MAILING)
    mail_logger.mailing("Checking mailing logs on init.")
    return mail_logger
