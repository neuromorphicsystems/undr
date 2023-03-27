import pathlib
import tempfile
import unittest

import undr.task

"""
with tempfile.TemporaryDirectory() as temporary_directory_name:
    temporary_directory = pathlib.Path(temporary_directory_name)
    with open(temporary_directory / "undr.toml", "w") as configuration_file:
        configuration_file.write(
            "\n".join(
                (
                    "directory = 'datasets'",
                    "",
                    "[[datasets]]",
                    "name = 'dvs09'",
                    "url = 'https://rds.westernsydney.edu.au/Institutes/MARCS/ICNS/UNDR/dvs09/'",
                    "mode = 'remote'",
                    "server_type = 'apache'",
                )
            )
        )
        configuration_file.write("\n")
    configuration = undr.Configuration(temporary_directory / "undr.toml")
"""
