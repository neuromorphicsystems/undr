from __future__ import annotations

import errno
import functools
import json
import pathlib

from . import constants, utilities

schema = utilities.load_schema("-index_schema.json")


class InstallError(FileNotFoundError):
    def __init__(self, path: pathlib.Path):
        super().__init__(errno.ENOENT, "", str(path))

    def __str__(self) -> str:
        return (
            f'"{self.filename}" does not exist, have you installed the configuration?'
        )


@functools.lru_cache(maxsize=constants.LRU_CACHE_MAXSIZE)
def load(path: pathlib.Path):
    try:
        with open(path) as index_data_file:
            index_data = json.load(index_data_file)
        schema.validate(index_data)
        return index_data
    except FileNotFoundError:
        raise InstallError(path)
