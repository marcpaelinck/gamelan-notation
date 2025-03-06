import logging

# List will collect all logging
LOGGING = []  # TODO operational but not yet in use

loggers: dict[str, logging.Logger] = {}


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    msgformat = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # (%(filename)s:%(lineno)d)"

    def __init__(self, colors=True):
        self.withcolors = colors

    FORMATS = {
        True: {
            logging.DEBUG: grey + msgformat + reset,
            logging.INFO: grey + msgformat + reset,
            logging.WARNING: yellow + msgformat + reset,
            logging.ERROR: red + msgformat + reset,
            logging.CRITICAL: bold_red + msgformat + reset,
            "datefmt": "%H:%M:%S",
        },
        False: {
            logging.DEBUG: msgformat,
            logging.INFO: msgformat,
            logging.WARNING: msgformat,
            logging.ERROR: msgformat,
            logging.CRITICAL: msgformat,
            "datefmt": "%H:%M:%S",
        },
    }

    def format(self, record):
        log_fmt = self.FORMATS[self.withcolors].get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)


class CustomHandler(logging.Handler):

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.setFormatter(CustomFormatter(False))

    def emit(self, record):
        msg = self.format(record)
        LOGGING.append(msg)


def get_logger(name) -> logging.Logger:
    if name in loggers:
        # logging.getLogger is supposed to return previously created logger instances,
        # but this doen't seem to work.
        return loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter())
    logger.addHandler(handler)
    logger.addHandler(CustomHandler())
    loggers[name] = logger
    return logger


if __name__ == "__main__":
    logger = get_logger("test")
    logger.error("Foutmelding!")
    print(LOGGING)
