"""Data loading and number formatting functions."""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import pkgutil
import typing

import jsonschema_rs

from . import constants


def load_schema(name: str) -> jsonschema_rs.JSONSchema:
    """Reads and parses a JSON schema bundled with UNDR.

    Args:
        name (str): Name of the schema.

    Returns:
        jsonschema_rs.JSONSchema: JSON schema validator.
    """
    data = pkgutil.get_data("undr", name)
    assert data is not None
    return jsonschema_rs.JSONSchema(json.loads(data.decode()))


def least_multiple_over_chunk_size(word_size: int) -> int:
    """Calculates the maximum number of bytes in a chunk that can be divided into full words.

    For instance, for a chunks size of 100 bytes and a word size of 32 bytes, this function would return 96.

    Args:
        word_size (int): The word size in bytes. The chunk size is not a parameter since UNDR always uses :py:attr:`undr.constants.CHUNK_SIZE`.

    Returns:
        int: Maximum number of bytes in a chunk that can be divided into full words. This number is guaranteed to be a multiple of word_size. It may be zero.
    """
    return word_size * int(math.ceil(constants.CHUNK_SIZE / word_size))


def path_with_suffix(path: pathlib.Path, suffix: str) -> pathlib.Path:
    """Appends a suffix to a path and returns a new path.

    Args:
        path (pathlib.Path): Input path, not modified by this function.
        suffix (str): The string to append to the path's last component.

    Returns:
        pathlib.Path: New path with the given suffix.
    """
    return pathlib.Path(f"{path}{suffix}")


def posix_path_with_suffix(
    path: pathlib.PurePosixPath, suffix: str
) -> pathlib.PurePosixPath:
    """Appends a suffix to a POSIX path and returns a new path.

    Similar to :py:func:`path_with_suffix` for POSIX paths.

    Args:
        path (pathlib.PurePosixPath): Input path, not modified by this function.
        suffix (str): The string to append to the path's last component.

    Returns:
        pathlib.PurePosixPath: New path with the given suffix.
    """
    return pathlib.PurePosixPath(f"{path}{suffix}")


def new_hash() -> "hashlib._Hash":
    """Creates a new byte hasher.

    Returns:
        hashlib._Hash: SHA3-224 (FIPS 202) hasher.
    """
    return hashlib.sha3_224()


def hash(chunks: typing.Iterable[bytes]) -> "hashlib._Hash":
    """Consumes an iterable and calculates a hash.

    Since this function consumes the hash, users should use :py:func:`new_hash` and call :py:meth:`hashlib._Hash.update` manually if they plan to do something else with the bytes.

    Args:
        chunks (typing.Iterable[bytes]): A bytes iterable.

    Returns:
        hashlib._Hash: SHA3-224 (FIPS 202) hasher. Use :py:meth:`hashlib._Hash.digest` or :py:meth:`hashlib._Hash.hexdigest` to read the hash value.
    """
    hash_object = new_hash()
    for chunk in chunks:
        hash_object.update(chunk)
    return hash_object


def hash_file(path: pathlib.Path, chunk_size: int):
    """Calculates a file's hash.

    Args:
        path (pathlib.Path): Path of the file to hash.
        chunk_size (int): Chunk size in bytes, used to read the file.

    Returns:
        _type_: _description_
    """
    with open(path, "rb") as input:
        return hash(iter(lambda: input.read(chunk_size), b""))


def duration_to_string(duration: float) -> str:
    """Generates a human-readable representation of a duration.

    Args:
        duration (float): Positive time delta in seconds.

    Returns:
        str: Human-redable representation.
    """
    duration = round(duration)
    if duration < 180:
        return f'{"{:.0f}".format(duration)} s'
    if duration < 10800:
        return f'{"{:.0f}".format(math.floor(duration / 60))} min'
    if duration < 259200:
        return f'{"{:.0f}".format(math.floor(duration / 3600))} h'
    return f'{"{:.0f}".format(math.floor(duration / 86400))} days'


def size_to_string(size: int) -> str:
    """Generates a human-readable representation of a size.

    Args:
        size (float): Resource size in bytes.

    Returns:
        str: Human-redable representation.
    """
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
    """Generates a human-readable representation of a speed.

    Args:
        speed (int): Download or process speed in bytes per second.

    Returns:
        str: Human-redable representation.
    """
    if speed < 1000:
        return f'{"{:.0f}".format(speed)} B/s'
    if speed < 1000000:
        return f'{"{:.2f}".format(speed / 1000)} kB/s'
    if speed < 1000000000:
        return f'{"{:.2f}".format(speed / 1000000)} MB/s'
    if speed < 1000000000000:
        return f'{"{:.2f}".format(speed / 1000000000)} GB/s'
    return f'{"{:.2f}".format(speed / 1000000000000)} TB/s'
