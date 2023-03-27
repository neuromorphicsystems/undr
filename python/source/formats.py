from __future__ import annotations

import dataclasses
import functools
import typing

import numpy

from . import path, raw

if typing.TYPE_CHECKING:
    from . import path_directory

try:
    functools.cached_property
except:
    functools.cached_property = property


@dataclasses.dataclass(frozen=True)
class ApsFile(path.File):
    width: int = dataclasses.field(compare=False, hash=False)
    height: int = dataclasses.field(compare=False, hash=False)

    @functools.cached_property
    def word_size(self):
        return raw.aps_dtype(self.width, self.height).itemsize

    def packets(self) -> typing.Iterable[numpy.ndarray]:
        dtype = numpy.dtype(raw.aps_dtype(self.width, self.height))
        for chunk in self._chunks(word_size=self.word_size):
            yield numpy.frombuffer(chunk, dtype=dtype)


@dataclasses.dataclass(frozen=True)
class DvsFile(path.File):
    width: int = dataclasses.field(compare=False, hash=False)
    height: int = dataclasses.field(compare=False, hash=False)

    @functools.cached_property
    def word_size(self):
        return raw.DVS_DTYPE.itemsize

    def packets(self) -> typing.Iterable[numpy.ndarray]:
        for chunk in self._chunks(word_size=self.word_size):
            yield numpy.frombuffer(chunk, dtype=raw.DVS_DTYPE)


@dataclasses.dataclass(frozen=True)
class ImuFile(path.File):
    @functools.cached_property
    def word_size(self):
        return raw.IMU_DTYPE.itemsize

    def packets(self) -> typing.Iterable[numpy.ndarray]:
        for chunk in self._chunks(word_size=self.word_size):
            yield numpy.frombuffer(chunk, dtype=raw.IMU_DTYPE)


def file_from_dict(
    data: dict[str, typing.Any], parent: path_directory.Directory
) -> path.File:
    file_attributes = path.File.attributes_from_dict(data=data, parent=parent)
    if data["properties"]["type"] == "aps":
        return ApsFile(
            **file_attributes,
            width=data["properties"]["width"],
            height=data["properties"]["height"],
        )
    if data["properties"]["type"] == "dvs":
        return DvsFile(
            **file_attributes,
            width=data["properties"]["width"],
            height=data["properties"]["height"],
        )
    if data["properties"]["type"] == "imu":
        return ImuFile(**file_attributes)
    raise RuntimeError(f"unsupported file type {type}")


SendMessage = typing.Callable[[typing.Any], None]


@dataclasses.dataclass
class Switch:
    handle_aps: typing.Optional[typing.Callable[[ApsFile, SendMessage], None]] = None
    handle_dvs: typing.Optional[typing.Callable[[DvsFile, SendMessage], None]] = None
    handle_imu: typing.Optional[typing.Callable[[ImuFile, SendMessage], None]] = None
    handle_other: typing.Optional[
        typing.Callable[[path.File, SendMessage], None]
    ] = None

    def enabled_types(self):
        result = set()
        if self.handle_aps is not None:
            result.add(ApsFile)
        if self.handle_dvs is not None:
            result.add(DvsFile)
        if self.handle_imu is not None:
            result.add(ImuFile)
        return result

    def handle_file(self, file: path.File, send_message: SendMessage):
        if self.handle_aps is not None and isinstance(file, ApsFile):
            self.handle_aps(file, send_message)
        elif self.handle_dvs is not None and isinstance(file, DvsFile):
            self.handle_dvs(file, send_message)
        elif self.handle_imu is not None and isinstance(file, ImuFile):
            self.handle_imu(file, send_message)
        elif self.handle_other is not None and file.__class__ == path.File:
            self.handle_other(file, send_message)
        else:
            raise Exception(f"unsupported file format {file.__class__}")
