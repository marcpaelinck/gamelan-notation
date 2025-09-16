import os
import unittest


def pytest_configure(config):  # pylint: disable=unused-argument
    """FOR PYTEST: loads a test-specific .env file before tests run."""
    os.environ["GAMELAN_NOTATION_CONFIG_PATH"] = "./tests/config/config.yaml"
    os.environ["GAMELAN_NOTATION_PARSER_SETTINGS_PATH"] = "./tests/config/notationparser.yaml"


class BaseUnitTestCase(unittest.TestCase):
    """FOR UNITTEST: subclass this TestCase class. Sets environment variables for testing"""

    @classmethod
    def setUpClass(cls):
        os.environ["GAMELAN_NOTATION_CONFIG_PATH"] = "./tests/config/config.yaml"
        os.environ["GAMELAN_NOTATION_PARSER_SETTINGS_PATH"] = "./tests/config/notationparser.yaml"
