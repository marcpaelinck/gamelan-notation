# Settings Module Documentation

## Overview
The `settings` folder contains modules that manage the project's settings. The settings indicate which data files should be used and which options should be activated. These modules are designed to centralize and streamline the configuration process, making it easier to manage and maintain the project's settings.

## Modules

### 1. `settings.py`
This module expands the run_settings.yaml settings by adding the corresponding data from the data.yaml file.
**data.yaml** - contains information about all the files in the data subfolders.
**run_settings.yaml** - contains references to the required input files together with options that can activate functionality of the application.

### 2. `settings_validation.py`
This module checks the consistency of the input data. Currently, only the font and midi data files are checked.

### 3. `font_to_valid_notes.py`
This module combines the font and midinotes files to create a list of all available notes (as dict[str, str] records) for each instrument position. This results in an implicit validation of the notation. Any position-note combination in the notation that can not be found in this list will cause a value error.

## Usage
To use a specific settings module, you need to set the `DJANGO_SETTINGS_MODULE` environment variable to the appropriate module path. For example, to use the development settings, you would set:
