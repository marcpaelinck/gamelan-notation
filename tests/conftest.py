# @pytest.fixture(scope="session", autouse=True)
# def load_test_env():
#     """Load a test-specific .env file before tests run."""
#     load_dotenv(".env.test", override=True)


import os


def pytest_configure(config):
    """Load a test-specific .env file before tests run."""
    os.environ["GAMELAN_NOTATION_CONFIG_PATH"] = "./tests/settings/config.yaml"
    os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/settings/notation2midi.yaml"
