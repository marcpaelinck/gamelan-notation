# Gamelan Notation
This application creates MIDI files from the notation of Balinese gamelan.

## Installation
    This project uses pyenv-win and pyenv-win-venv for Windows
    See https://pyenv-win.github.io/pyenv-win/ and https://github.com/pyenv-win/pyenv-win-venv

    To install a python version (if not available yet):
    ```
        venv install <python version>
    ```

    To create and activate an environment:
    ```
    pyenv-venv install <python version> <environment name>
    pyenv-venv activate <environment name>
    ```
2.  Install Poetry, see https://python-poetry.org/docs/. Then install dependencies with the command:
    ```
    poetry install
    ```

## File encoding
Be sure to save the csv files as UTF-8 encoded (many text editors such as TextPad let the user select this option when saving a file).

# Terminology
`Muted`: key instruments: the key is muted with the left hand while striking it. Reyong: only used for `jet`: strike the gongs without lifting the panggul.
`Abbreviated`: key instruments: the key is muted shortly after being stricken. Reyong: only used for `byot`: strike the gongs and then immediately mute them.