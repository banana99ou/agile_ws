import logging
from io import StringIO


class Logger:
    def __init__(self, name=None):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._log_stringio_obj = StringIO()

        if not self._logger.hasHandlers():
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)

            formatter = logging.Formatter("[%(name)s](%(levelname)s) %(message)s")
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

        string_io_log_handler = logging.StreamHandler(self._log_stringio_obj)
        self._logger.addHandler(string_io_log_handler)

    def debug(self, message):
        self._logger.debug(message)

    def info(self, message):
        self._logger.info(message)

    def warn(self, message):
        self._logger.warning(message)

    def error(self, message):
        self._logger.error(message)

    def exception(self, message):
        self._logger.exception(message)

    @property
    def log_messages(self):
        return self._log_stringio_obj.getvalue()
