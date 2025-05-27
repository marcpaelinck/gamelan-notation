import os
import unittest


def pytest_configure(config):  # pylint: disable=unused-argument
    """FOR PYTEST: loads a test-specific .env file before tests run."""
    os.environ["GAMELAN_NOTATION_CONFIG_PATH"] = "./tests/config/config.yaml"
    os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/config/notation2midi.yaml"
    os.environ["GAMELAN_NOTATION_NOTATIONDOCS_PATH"] = "./tests/config/notations.yaml"


class BaseUnitTestCase(unittest.TestCase):
    """FOR UNITTEST: subclass this TestCase class. Sets environment variables for testing"""

    @classmethod
    def setUpClass(cls):
        os.environ["GAMELAN_NOTATION_CONFIG_PATH"] = "./tests/config/config.yaml"
        os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/config/notation2midi.yaml"
        os.environ["GAMELAN_NOTATION_NOTATIONDOCS_PATH"] = "./tests/config/notations.yaml"
