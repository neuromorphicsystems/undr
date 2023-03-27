from __future__ import annotations

import collections
import dataclasses
import itertools
import json
import pathlib
import typing

import numpy

from . import decode, formats, json_index, path, path_directory, utilities


@dataclasses.dataclass
class Error:
    path_id: pathlib.PurePosixPath
    message: str


def handle_aps(file: formats.ApsFile, send_message: formats.SendMessage):
    non_monotonic_ts = 0
    size_mismatches = 0
    empty = True
    try:
        previous_t = 0
        for frames in file.packets():
            empty = False
            if len(frames) > 0 and frames["t"][0] < previous_t:
                non_monotonic_ts += 1
                previous_t = frames["t"][-1]
            non_monotonic_ts += numpy.count_nonzero(
                numpy.diff(frames["t"].astype("<i8")) < 0
            )
            size_mismatches = numpy.count_nonzero(
                numpy.logical_or(
                    frames["width"] != file.width, frames["height"] != file.height
                )
            )
    except decode.RemainingBytesError as error:
        empty = False
        send_message(
            Error(path_id=file.path_id, message=f"{len(error.buffer)} extra bytes")
        )
    if empty:
        send_message(Error(path_id=file.path_id, message="no data found"))
    if non_monotonic_ts > 0:
        send_message(
            Error(
                path_id=file.path_id,
                message="{} non-monotonic timestamp{}".format(
                    non_monotonic_ts, "s" if non_monotonic_ts > 1 else ""
                ),
            )
        )
    if size_mismatches > 0:
        send_message(
            Error(
                path_id=file.path_id,
                message="{} size mismatch{}".format(
                    size_mismatches, "es" if size_mismatches > 1 else ""
                ),
            )
        )


def handle_dvs(file: formats.DvsFile, send_message: formats.SendMessage):
    non_monotonic_ts = 0
    out_of_bounds_count = 0
    empty = True
    try:
        previous_t = 0
        for events in file.packets():
            empty = False
            if len(events) > 0 and events["t"][0] < previous_t:
                non_monotonic_ts += 1
                previous_t = events["t"][-1]
            non_monotonic_ts += numpy.count_nonzero(
                numpy.diff(events["t"].astype("<i8")) < 0
            )
            out_of_bounds_count += numpy.count_nonzero(
                numpy.logical_or(events["x"] >= file.width, events["y"] >= file.height)
            )
    except decode.RemainingBytesError as error:
        empty = False
        send_message(
            Error(path_id=file.path_id, message=f"{len(error.buffer)} extra bytes")
        )
    if empty:
        send_message(Error(path_id=file.path_id, message="no data found"))
    if out_of_bounds_count > 0:
        send_message(
            Error(
                path_id=file.path_id,
                message="{} event{} out of bounds".format(
                    out_of_bounds_count, "s" if out_of_bounds_count > 1 else ""
                ),
            )
        )
    if non_monotonic_ts > 0:
        send_message(
            Error(
                path_id=file.path_id,
                message="{} non-monotonic timestamp{}".format(
                    non_monotonic_ts, "s" if non_monotonic_ts > 1 else ""
                ),
            )
        )


def handle_imu(file: formats.ImuFile, send_message: formats.SendMessage):
    non_monotonic_ts = 0
    empty = True
    try:
        previous_t = 0
        for imus in file.packets():
            empty = False
            if len(imus) > 0 and imus["t"][0] < previous_t:
                non_monotonic_ts += 1
                previous_t = imus["t"][-1]
            non_monotonic_ts += numpy.count_nonzero(
                numpy.diff(imus["t"].astype("<i8")) < 0
            )
    except decode.RemainingBytesError as error:
        send_message(
            Error(path_id=file.path_id, message=f"{len(error.buffer)} extra bytes")
        )
    if empty:
        send_message(Error(path_id=file.path_id, message="no data found"))
    if non_monotonic_ts > 0:
        send_message(
            Error(
                path_id=file.path_id,
                message="{} non-monotonic timestamp{}".format(
                    non_monotonic_ts, "s" if non_monotonic_ts > 1 else ""
                ),
            )
        )


def handle_other(file: path.File, send_message: formats.SendMessage):
    collections.deque(file.chunks(), maxlen=0)


def handle_directory(
    directory: path_directory.Directory, send_message: formats.SendMessage
):
    index_data = json_index.load(directory.local_path / "-index.json")
    children = set(directory.local_path.iterdir())
    for file in itertools.chain(
        (
            formats.file_from_dict(data=data, parent=directory)
            for data in index_data["files"]
        ),
        (
            path.File.from_dict(data=data, parent=directory)
            for data in index_data["other_files"]
        ),
    ):
        local_path = utilities.path_with_suffix(
            file.local_path, file.best_compression.suffix
        )
        if not local_path in children:
            raise Exception(f"{local_path} does not exist")
        children.remove(local_path)
        if not local_path.is_file():
            raise Exception(f"{local_path} is not a file")
    for child_directory_name in index_data["directories"]:
        directory_path = directory.local_path / child_directory_name
        if not directory_path in children:
            raise Exception(f"{directory_path} does not exist")
        children.remove(directory_path)
        if not directory_path.is_dir():
            raise Exception(f"{directory_path} is not a directory")
    for child in children:
        if child.name != "-index.json":
            raise Exception(
                f"{child} is not listed in {directory.local_path / '-index.json'}"
            )


def structure_recursive(path: pathlib.Path):
    if not path.exists():
        raise Exception(f"{path} does not exist")
    if not path.is_dir():
        raise Exception(f"{path} is not a directory")
    index_path = path / "-index.json"
    if not index_path.exists():
        raise Exception(f"{index_path} does not exist")
    if not index_path.is_file():
        raise Exception(f"{index_path} is not a file")
    index_data = json_index.load(index_path)
    for child_directory_name in index_data["directories"]:
        structure_recursive(path / child_directory_name)


def format_index_recursive(
    path: pathlib.Path, handle_path: typing.Callable[[pathlib.Path], None]
):
    index_path = path / "-index.json"
    with open(index_path, "rb") as index_file:
        index_content = index_file.read()
    index_data = json.loads(index_content)
    json_index.schema.validate(index_data)
    new_index_content = f"{json.dumps(index_data, sort_keys=True, indent=4)}\n".encode()
    if index_content != new_index_content:
        handle_path(index_path)
        with open(index_path, "wb") as index_file:
            index_file.write(new_index_content)
    for child_directory_name in index_data["directories"]:
        format_index_recursive(
            path=path / child_directory_name, handle_path=handle_path
        )
