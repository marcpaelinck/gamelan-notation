import logging


class CustomFormatter(logging.Formatter):
    """Formats time and adds colors to logging depending on logging level"""

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    msgformat = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # (%(filename)s:%(lineno)d)"

    def __init__(self, colors=True):
        super().__init__(fmt=self.msgformat)
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
    """Uses the CustomFormatter and saves logging to a list (not in use yet)."""

    def __init__(self, logging_storage: list[str]):
        super().__init__(level=logging.INFO)
        self.setFormatter(CustomFormatter(False))
        self.logging_storage = logging_storage

    def emit(self, record):
        msg = self.format(record)
        self.logging_storage.append(msg)


class CustomLogger:
    """Logger with added 'progress bar' facility (dots)"""

    def __init__(self, name: str, handler: CustomHandler):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.handler = logging.StreamHandler()
        self.handler.setFormatter(CustomFormatter())
        self.logger.addHandler(self.handler)
        self.logger.addHandler(handler)
        self.dot_count = 0
        self.last_message_len = 0

    def log(self, level: int, msg: object, *args, **kwargs):
        self.logger.log(level, msg, *args, **kwargs)

    def info(self, msg: object, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: object, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def error(self, msg: object, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def log_progress(self, message=""):
        """Logs the provided message and appends a dot, overwriting the previous line."""
        if message:
            # Clear the previous line by overwriting it with spaces.
            clear_line = " " * self.last_message_len
            self.handler.stream.write(f"\r{clear_line}\r{message}")
            self.handler.stream.flush()  # ensure the output is shown immediately
            self.last_message_len = len(message)
            self.dot_count = 0  # reset dot count
        else:
            self.handler.stream.write(".")
            self.handler.stream.flush()
            self.dot_count += 1
            self.last_message_len += 1  # consider the dot in the length calculation

    def log_final(self, message, newline=False):
        """Logs a final message without overwriting the line."""
        clear_line = " " * self.last_message_len
        self.handler.stream.write(f"\r{clear_line}\r{message}{'\n' if newline else ""}")  # newline to go to next line
        self.handler.stream.flush()
        self.last_message_len = 0
        self.dot_count = 0

    def open_logging(self, message: str):
        """To be called by the main program before the first parsing step.
        Adds an empty line followed by a title line"""
        separator = "=" * int(50 - len(message) // 2)
        title = f"{separator} {message} {separator}"
        # self.logger.info("")
        self.logger.info(title)

    def close_logging(self):
        """To be called by the main program after the last parsing step.
        Draws a double line (===) followed by an empty line"""
        self.logger.info("=" * 102)
        self.logger.info("")


class Logging:
    """Static class, should be used to create a logger for a specific module."""

    # List will collect all logging
    LOGGING = []  # TODO operational but not yet in use
    loggers: dict[str, logging.Logger] = {}

    @classmethod
    def get_logger(cls, name: str) -> CustomLogger:
        """Returns a new logger or an existing one if a logger with the given name already exists.
        Module name should be passed as argument."""
        if name in cls.loggers:
            # logging.getLogger is supposed to avoid creating multiple loggers with the same name,
            # but this doen't seem to work.
            return cls.loggers[name]
        logger = CustomLogger(name, CustomHandler(cls.LOGGING))
        cls.loggers[name] = logger
        return logger


if __name__ == "__main__":
    # For testing
    testlogger = Logging.get_logger("test")
    testlogger.error("Error!")
    print(Logging.LOGGING)
