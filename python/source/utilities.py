from __future__ import annotations

import hashlib
import json
import math
import pathlib
import pkgutil
import typing

import jsonschema_rs

from . import constants


def load_schema(name: str):
    data = pkgutil.get_data("undr", name)
    assert data is not None
    return jsonschema_rs.JSONSchema(json.loads(data.decode()))


def least_multiple_over_chunk_size(word_size: int):
    return word_size * math.ceil(constants.CHUNK_SIZE / word_size)


def path_with_suffix(path: pathlib.Path, suffix: str) -> pathlib.Path:
    return pathlib.Path(f"{path}{suffix}")


def posix_path_with_suffix(
    path: pathlib.PurePosixPath, suffix: str
) -> pathlib.PurePosixPath:
    return pathlib.PurePosixPath(f"{path}{suffix}")


def new_hash() -> "hashlib._Hash":
    return hashlib.sha3_224()


def hash(chunks: typing.Iterable[bytes]) -> "hashlib._Hash":
    hash_object = new_hash()
    for chunk in chunks:
        hash_object.update(chunk)
    return hash_object


def hash_file(path: pathlib.Path, chunk_size: int):
    with open(path, "rb") as input:
        return hash(iter(lambda: input.read(chunk_size), b""))


def parse_size(size: str) -> int:
    if size[-1] == "K":
        return round(float(size[:-1]) * 1024)
    if size[-1] == "M":
        return round(float(size[:-1]) * (1024**2))
    if size[-1] == "G":
        return round(float(size[:-1]) * (1024**3))
    if size[-1] == "T":
        return round(float(size[:-1]) * (1024**4))
    return round(float(size))


def duration_to_string(duration: float) -> str:
    duration = round(duration)
    if duration < 180:
        return f'{"{:.0f}".format(duration)} s'
    if duration < 10800:
        return f'{"{:.0f}".format(math.floor(duration / 60))} min'
    if duration < 259200:
        return f'{"{:.0f}".format(math.floor(duration / 3600))} h'
    return f'{"{:.0f}".format(math.floor(duration / 86400))} days'


def size_to_string(size: int) -> str:
    if size < 1000:
        return f'{"{:.0f}".format(size)} B'
    if size < 1000000:
        return f'{"{:.2f}".format(size / 1000)} kB'
    if size < 1000000000:
        return f'{"{:.2f}".format(size / 1000000)} MB'
    if size < 1000000000000:
        return f'{"{:.2f}".format(size / 1000000000)} GB'
    return f'{"{:.2f}".format(size / 1000000000000)} TB'


def speed_to_string(speed: int) -> str:
    if speed < 1000:
        return f'{"{:.0f}".format(speed)} B/s'
    if speed < 1000000:
        return f'{"{:.2f}".format(speed / 1000)} kB/s'
    if speed < 1000000000:
        return f'{"{:.2f}".format(speed / 1000000)} MB/s'
    if speed < 1000000000000:
        return f'{"{:.2f}".format(speed / 1000000000)} GB/s'
    return f'{"{:.2f}".format(speed / 1000000000000)} TB/s'


class InlineEncoder(json.JSONEncoder):
    def __init__(
        self, maximum_length: int, indent: int, *args: typing.Any, **kwargs: typing.Any
    ):
        super().__init__(*args, indent=indent, **kwargs)
        self.inline_encoder = json.JSONEncoder(*args, indent=None, **kwargs)
        self.maximum_length = maximum_length
        self.prefix = ""
        self.indent_level = 0

    def encode(self, o: typing.Any):
        inline = self.inline_encoder.encode(o)
        if len(inline) <= self.maximum_length - len(self.prefix):
            return inline
        if isinstance(o, (list, tuple)):
            self.indent_level += 1
            self.prefix = " " * (self.indent * self.indent_level)
            items = tuple(
                f"{self.prefix}{self.encode(item)}"
                for item in typing.cast(list[typing.Any], o)
            )
            self.indent_level -= 1
            self.prefix = " " * (self.indent * self.indent_level)
            return "[\n{}\n{}]".format(",\n".join(items), self.prefix)
        if isinstance(o, dict):
            self.indent_level += 1
            self.prefix = " " * (self.indent * self.indent_level)
            entries: list[str] = []
            for key, value in typing.cast(dict[str, typing.Any], o).items():
                self.prefix = '{}"{}": '.format(
                    " " * (self.indent * self.indent_level), key
                )
                entries.append(f"{self.prefix}{self.encode(value)}")
            self.indent_level -= 1
            self.prefix = " " * (self.indent * self.indent_level)
            return "{{\n{}\n{}}}".format(",\n".join(entries), self.prefix)
        return inline

    def iterencode(
        self, o: typing.Any, _one_shot: bool, **kwargs: typing.Any
    ) -> typing.Iterator[str]:
        yield self.encode(o)
