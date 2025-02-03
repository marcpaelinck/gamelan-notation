# import pytest
# from pytest import MonkeyPatch

# import src.settings.settings
# from src.settings.constants import Yaml
# from src.settings.settings import get_run_settings


# @pytest.fixture(scope="module", autouse=True)
# # Monkeypatch version for module scope.
# # Source: https://stackoverflow.com/questions/53963822/python-monkeypatch-setattr-with-pytest-fixture-at-module-scope
# def monkeymodule():
#     mpatch = MonkeyPatch()
#     yield mpatch
#     mpatch.undo()


# @pytest.fixture(scope="module", autouse=True)
# def run_settings(monkeymodule):
#     monkeymodule.setattr(src.settings.settings, "SETTINGSFOLDER", "./tests/settingsfiles")
#     settings = get_run_settings()
#     return settings
