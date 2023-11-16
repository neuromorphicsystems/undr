"""Basic index files parsing."""

from __future__ import annotations

import errno
import functools
import json
import pathlib
import typing

from . import constants, utilities

validate = utilities.load_schema("-index_schema")
"""JSON schema validator for -index files."""


class InstallError(FileNotFoundError):
    """Raised if the target path does not exist.

    Args:
        path (pathlib.Path): The path that does not exist.
    """

    def __init__(self, path: pathlib.Path):
        super().__init__(errno.ENOENT, "", str(path))

    def __str__(self) -> str:
        return (
            f'"{self.filename}" does not exist, have you installed the configuration?'
        )


@functools.lru_cache(maxsize=constants.LRU_CACHE_MAXSIZE)
def load(path: pathlib.Path) -> dict[str, typing.Any]:
    """Reads and validates a -index.json file.

    This function caches the parsed contents of up to :py:attr:`undr.constants.LRU_CACHE_MAXSIZE` files.

    Args:
        path (pathlib.Path): The path of the file to read.

    Raises:
        InstallError: if the file does not exist.
        fastjsonschema.JsonSchemaValueException: if validation fails.

    Returns:
        dict[str, typing.Any]: Parsed JSON file contents.
    """

    try:
        with open(path) as index_data_file:
            index_data = json.load(index_data_file)
        validate(index_data)
        return index_data
    except FileNotFoundError:
        raise InstallError(path)
