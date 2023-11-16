"""Implementation of datasets conformity tests (file structure, hashes, event coordinates...)."""

from __future__ import annotations

import collections
import dataclasses
import itertools
import json
import pathlib
import typing

import numpy
import requests

from . import (
    decode,
    formats,
    json_index,
    json_index_tasks,
    path,
    path_directory,
    remote,
    task,
    utilities,
)


@dataclasses.dataclass
class Error:
    """Reports invariant violations while checking data files."""

    path_id: pathlib.PurePosixPath
    """Identifier of the problematic resource.
    """

    message: str
    """Description of the problem.
    """


def handle_aps(file: formats.ApsFile, send_message: formats.SendMessage):
    """Checks the invariants of an APS file.

    Args:
        file (formats.ApsFile): The file to check.
        send_message (formats.SendMessage): Callback channel for errors.
    """
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
    """Checks the invariants of a DVS file.

    Args:
        file (formats.DvsFile): The file to check.
        send_message (formats.SendMessage): Callback channel for errors.
    """
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
    """Checks the invariants of an IMU file.

    Args:
        file (formats.ImuFile): The file to check.
        send_message (formats.SendMessage): Callback channel for errors.
    """
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
    """Checks the invariants of an "other" file.

    This function simply consumes the file bytes.
    This guarantees that the file can be read and that the index contains the right hash and number of bytes.

    Args:
        file (formats.ImuFile): The file to check.
        send_message (formats.SendMessage): Callback channel for errors.
    """
    collections.deque(file.chunks(), maxlen=0)


def handle_directory(
    directory: path_directory.Directory, send_message: formats.SendMessage
):
    """Checks that system files are listed in the index, and vice-versa.

    Args:
        directory (path_directory.Directory): The directory to check.
        send_message (formats.SendMessage): Callback channel for errors.
    """
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
            send_message(
                Error(
                    path_id=file.path_id,
                    message=f"{local_path} does not exist",
                )
            )
        children.remove(local_path)
        if not local_path.is_file():
            send_message(
                Error(
                    path_id=file.path_id,
                    message=f"{local_path} is not a file",
                )
            )
    for child_directory_name in index_data["directories"]:
        directory_path = directory.local_path / child_directory_name
        if not directory_path in children:
            send_message(
                Error(
                    path_id=directory.path_id,
                    message=f"{directory_path} does not exist",
                )
            )
        children.remove(directory_path)
        if not directory_path.is_dir():
            send_message(
                Error(
                    path_id=directory.path_id,
                    message=f"{directory_path} is not a directory",
                )
            )
    for child in children:
        if child.name != "-index.json":
            send_message(
                Error(
                    path_id=directory.path_id,
                    message=f"{child} is not listed in {directory.local_path / '-index.json'}",
                )
            )


def structure_recursive(path: pathlib.Path):
    """Rexucrively checks that the given path exists and that it has an UNDR structure (-index.json).

    Args:
        path (pathlib.Path): The local file path to check.

    Raises:
        RuntimeError: if the path is not a directory or does not contain a -index.json file.
    """
    if not path.exists():
        raise RuntimeError(f"{path} does not exist")
    if not path.is_dir():
        raise RuntimeError(f"{path} is not a directory")
    index_path = path / "-index.json"
    if not index_path.exists():
        raise RuntimeError(f"{index_path} does not exist")
    if not index_path.is_file():
        raise RuntimeError(f"{index_path} is not a file")
    index_data = json_index.load(index_path)
    for child_directory_name in index_data["directories"]:
        structure_recursive(path / child_directory_name)


def format_index_recursive(
    path: pathlib.Path, handle_path: typing.Callable[[pathlib.Path], None]
):
    """Validates the given index and formats its content.

    Args:
        path (pathlib.Path): Path of the index's parent directory.
        handle_path (typing.Callable[[pathlib.Path], None]): Called if the index was reformatted.
    """
    index_path = path / "-index.json"
    with open(index_path, "rb") as index_file:
        index_content = index_file.read()
    index_data = json.loads(index_content)
    json_index.validate(index_data)
    new_index_content = f"{json.dumps(index_data, sort_keys=True, indent=4)}\n".encode()
    if index_content != new_index_content:
        handle_path(index_path)
        with open(index_path, "wb") as index_file:
            index_file.write(new_index_content)
    for child_directory_name in index_data["directories"]:
        format_index_recursive(
            path=path / child_directory_name, handle_path=handle_path
        )


class CheckFile(json_index_tasks.ProcessFile):
    """Uses a switch to process files and wraps messages into :py:class:`undr.check.Error`.

    Args:
        file (path.File): The file to process.
        switch (formats.Switch): Switch that maps file types to actions.
    """

    def __init__(self, file: path.File, switch: formats.Switch):
        super().__init__(file=file)
        self.switch = switch

    def run(self, session: requests.Session, manager: task.Manager):
        self.file.attach_session(session)
        self.file.attach_manager(manager)
        self.switch.handle_file(
            file=self.file,
            send_message=lambda message: manager.send_message(
                Error(path_id=self.file.path_id, message=message)
            ),
        )


class CheckLocalDirectoryRecursive(task.Task):
    """Dispatches check actions to validate the invariants of local files.

    This can be used to make sure that a dataset has been properly downloaded or to check files before uploading a dataset to a server.

    Args:
        path_root (pathlib.Path): The root path used to generate local file paths.
        path_id (pathlib.PurePosixPath): The path ID of the directory that will be scanned recursively.
        priority (int): Priority of this task and all recursively created tasks (tasks with lower priorities are scheduled first).
    """

    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        priority: int,
    ):
        self.path_root = path_root
        self.path_id = path_id
        self.priority = priority

    def run(self, session: requests.Session, manager: task.Manager):
        directory = path_directory.Directory(
            path_root=self.path_root,
            path_id=self.path_id,
            own_doi=None,
            metadata={},
            server=remote.NullServer(),
            doi_and_metadata_loaded=False,
        )
        handle_directory(
            directory=directory,
            send_message=lambda message: manager.send_message(
                Error(path_id=directory.path_id, message=message)
            ),
        )
        index_data = json_index.load(directory.local_path / "-index.json")
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
            manager.schedule(
                CheckFile(
                    file=file,
                    switch=formats.Switch(
                        handle_aps=handle_aps,
                        handle_dvs=handle_dvs,
                        handle_imu=handle_imu,
                        handle_other=handle_other,
                    ),
                ),
                priority=self.priority,
            )
        for child_directory_name in index_data["directories"]:
            manager.schedule(
                CheckLocalDirectoryRecursive(
                    path_root=self.path_root,
                    path_id=self.path_id / child_directory_name,
                    priority=self.priority,
                ),
                priority=self.priority,
            )
