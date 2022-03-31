from __future__ import annotations
from lzip import RemainingBytesError
import collections
import dataclasses
import itertools
import numpy
import pathlib
import typing
from . import formats
from . import json_index
from . import path
from . import path_directory
from . import remote


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
    except RemainingBytesError as error:
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
    except RemainingBytesError as error:
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
    except RemainingBytesError as error:
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


def directory(
    path_root: pathlib.Path, path_id: pathlib.PurePosixPath, allow_uncompressed: bool
):
    pass


"""
def local_directory(
    directory: path_directory.Directory,
    delete_dot_files: bool,
    format_index: bool,
    send_message: typing.Callable[[pathlib.PurePosixPath, str], None],
) -> None:
    for child_path in directory.iter(recursive=True):
        if isinstance(child_path, path_directory.Directory):
            pass
        elif isinstance(child_path, formats.ApsFile):
            aps_file(file=child_path, send_message=send_message)
        elif isinstance(child_path, formats.DvsFile):
            dvs_file(file=child_path, send_message=send_message)
        elif isinstance(child_path, formats.ImuFile):
            imu_file(file=child_path, send_message=send_message)
        elif child_path.__class__ == path.File:
            other_file(file=child_path, send_message=send_message)  # type: ignore
        else:
            raise Exception(f"unexpected path type {child_path.__class__}")


    for path in sorted(directory.path.iterdir()):
        if path.is_file():
            if path.name == "-index.json":
                continue
            if path.suffix == ".lz":
                if (
                    not path.stem in directory.files
                    and not path.stem in directory.other_files
                ):
                    print(
                        progress.format_error(
                            'the file "{}" is not listed in "{}" (compressed files must be listed without their .lz extension)'.format(
                                path, directory.path / "-index.json"
                            )
                        )
                    )
            elif (
                not path.name in directory.files
                and not path.name in directory.other_files
            ):
                if delete_ds_store and path.name == ".DS_Store":
                    path.unlink()
                    print(f"🦘 deleted {path}")
                else:
                    print(
                        progress.format_error(
                            'the file "{}" is not listed in "{}"'.format(
                                path, directory.path / "-index.json"
                            )
                        )
                    )
        elif path.is_dir():
            if path.name in directory.directories:
                check_local_directory(
                    directory=directory.directories[path.name],
                    delete_ds_store=delete_ds_store,
                    format_index=format_index,
                )
            else:
                print(
                    progress.format_error(
                        'the directory "{}" is not listed in "{}"'.format(
                            path, directory.path / "-index.json"
                        )
                    )
                )
    if format_index:

        def sorted_copy(source: dict, first_keys: tuple[str]) -> dict:
            result = {}
            for key in first_keys:
                if key in source:
                    if isinstance(source[key], dict):
                        result[key] = sorted_copy(source[key], first_keys)
                    else:
                        result[key] = source[key]
            for key in sorted(source.keys()):
                if not key in result:
                    if isinstance(source[key], dict):
                        result[key] = sorted_copy(source[key], first_keys)
                    else:
                        result[key] = source[key]
            return result

        with open(directory.path / "-index.json") as json_index_file:
            raw_json_data = json_index_file.read()
        original_json_index = json.loads(raw_json_data)
        json_index_schema.validate(original_json_index)
        json_index = {}
        for key in sorted(original_json_index.keys()):
            json_index[key] = original_json_index[key]
        json_index["directories"].sort(key=lambda path: path["name"])
        json_index["files"].sort(key=lambda path: path["name"])
        json_index["other_files"].sort(key=lambda path: path["name"])
        for index in range(0, len(json_index["files"])):
            original_file = json_index["files"][index]
            file = {
                "name": original_file["name"],
                "size": original_file["size"],
                "sha3_224": original_file["sha3_224"],
                "properties": sorted_copy(
                    original_file["properties"], ("type", "width", "height")
                ),
                "metadata": sorted_copy(original_file["metadata"], ()),
                "compressions": [
                    sorted_copy(compression, ("type", "size", "sha3_224", "suffix"))
                    for compression in sorted(
                        original_file["compressions"], key=operator.itemgetter("suffix")
                    )
                ],
            }
            for key in sorted(original_file.keys()):
                if not key in file:
                    file[key] = sorted_copy(original_file[key], ())
            json_index["files"][index] = file
        for index in range(0, len(json_index["other_files"])):
            original_other_file = json_index["other_files"][index]
            other_file = {
                "name": original_other_file["name"],
                "size": original_other_file["size"],
                "sha3_224": original_other_file["sha3_224"],
                "metadata": sorted_copy(original_other_file["metadata"], ()),
                "compression": sorted_copy(
                    original_other_file["compression"], ("type", "size")
                ),
            }
            for key in sorted(original_other_file.keys()):
                if not key in other_file:
                    other_file[key] = sorted_copy(original_other_file[key], ())
            json_index["other_files"][index] = other_file
        new_raw_json_data = f"{json.dumps(json_index, cls=utilities.InlineEncoder, indent=4, maximum_length=80)}\n"
        if raw_json_data != new_raw_json_data:
            with open(directory.path / "-index.json", "w") as json_index_file:
                json_index_file.write(new_raw_json_data)
            print("🦘 formatted {}".format(directory.path / "-index.json"))def check_aps_file(file: ApsFile) -> set[str]:
    errors: set[str] = set()
    if file.width is None:
        send_message("missing width")
    if file.height is None:
        send_message("missing height")
    if len(errors) == 0:
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
        except RemainingBytesError as error:
            empty = False
            send_message(f"{len(error.buffer)} extra bytes")
        if empty:
            send_message("no data found")
        if non_monotonic_ts > 0:
            send_message(
                "{} non-monotonic timestamp{}".format(
                    non_monotonic_ts, "s" if non_monotonic_ts > 1 else ""
                )
            )
        if size_mismatches > 0:
            send_message(
                "{} size mismatch{}".format(
                    size_mismatches, "es" if size_mismatches > 1 else ""
                )
            )
    return errors
"""
