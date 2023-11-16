"""File formats supported by UNDR.

File types that are not listed here can still be included, downloaded, decompressed, and checked with UNDR. However, they are listed as "other files" and UNDR does not attempt to parse or load them.

To add a new file format, create and implement a derived class of :py:class:`undr.path.File` (see for instance :py:class:`ApsFile`) and add it to :py:func:`file_from_dict` and :py:class:`Switch`.
"""

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
    """A file that contains luminance (grey levels) frames.

    Active-pixel sensors (APS) describe, strictly speaking, any sensor with pixels that use MOSFET amplifiers.
    However, the term is commonly used to refer to the integrating pixels found in non-CCD conventional cameras.
    In the context of Neuromorphic Engineering, APS is used to describe DAVIS frames.
    """

    width: int = dataclasses.field(compare=False, hash=False)
    """Frame width (x direction) in pixels.
    """

    height: int = dataclasses.field(compare=False, hash=False)
    """Frame height (y direction) in pixels.
    """

    @functools.cached_property
    def word_size(self) -> int:
        return raw.aps_dtype(self.width, self.height).itemsize  # typr: ignore

    def packets(self) -> typing.Iterable[numpy.ndarray]:
        """Iterates over the file data.

        This function streams the file from the remote server if it is not available locally, and decompresses the file in memory if it is locally available but compressed.

        Returns:
            typing.Iterable[numpy.ndarray]: Iterator over the file's data converted into numpy arrays with dtype :py:func:`undr.raw.aps_dtype`.
        """
        dtype = numpy.dtype(raw.aps_dtype(self.width, self.height))
        for chunk in self._chunks(word_size=self.word_size):
            yield numpy.frombuffer(chunk, dtype=dtype)


@dataclasses.dataclass(frozen=True)
class DvsFile(path.File):
    """A file that contains DVS (polarity) events.

    Dynamic Vision Sensor events, often called polarity events,
    contain a timestamp, pixel coordinates, and a polarity (ON or OFF)
    that indicates whether luminance increased or decreased.
    """

    width: int = dataclasses.field(compare=False, hash=False)
    """Frame width (x direction) in pixels.
    """

    height: int = dataclasses.field(compare=False, hash=False)
    """Frame height (y direction) in pixels.
    """

    @functools.cached_property
    def word_size(self):
        return raw.DVS_DTYPE.itemsize

    def packets(self) -> typing.Iterable[numpy.ndarray]:
        """Iterates over the file data.

        This function streams the file from the remote server if it is not available locally, and decompresses the file in memory if it is locally available but compressed.

        Returns:
            typing.Iterable[numpy.ndarray]: Iterator over the file's data converted into numpy arrays with dtype :py:attr:`undr.raw.DVS_DTYPE`.
        """
        for chunk in self._chunks(word_size=self.word_size):
            yield numpy.frombuffer(chunk, dtype=raw.DVS_DTYPE)


@dataclasses.dataclass(frozen=True)
class ImuFile(path.File):
    """A file that contains IMU events.

    Inertial Measurement Unit (IMU) events are produced by an accelerometer / gyroscope / magnetometer.
    """

    @functools.cached_property
    def word_size(self):
        return raw.IMU_DTYPE.itemsize

    def packets(self) -> typing.Iterable[numpy.ndarray]:
        """Iterates over the file data.

        This function streams the file from the remote server if it is not available locally, and decompresses the file in memory if it is locally available but compressed.

        Returns:
            typing.Iterable[numpy.ndarray]: Iterator over the file's data converted into numpy arrays with dtype :py:attr:`undr.raw.IMU_DTYPE`.
        """
        for chunk in self._chunks(word_size=self.word_size):
            yield numpy.frombuffer(chunk, dtype=raw.IMU_DTYPE)


def file_from_dict(
    data: dict[str, typing.Any],
    parent: path_directory.Directory,
) -> path.File:
    """Creates a file object from a dictionary, typically loaded from an index file.

    Args:
        data (dict[str, typing.Any]): Dictionary describing the file and its properties.
        parent (path_directory.Directory): Parent directory of the file, used to generate the file system path.

    Raises:
        RuntimeError: if the file type is not supported by this function.

    Returns:
        path.File: A specialized file object.
    """
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
"""Callback channel for messages generated by a file handler during data iteration.
"""


@dataclasses.dataclass
class Switch:
    """Calls specialized file handlers while iterating a dataset.

    If a handler is None, the corresponding files are ignored by the iterator.

    Args:
        handle_aps (typing.Optional[typing.Callable[[ApsFile, SendMessage], None]]): Handler for APS files.
        handle_dvs (typing.Optional[typing.Callable[[DvsFile, SendMessage], None]]): Handler for DVS files.
        handle_imu (typing.Optional[typing.Callable[[ImuFile, SendMessage], None]]): Handler for IMU files.
        handle_other (typing.Optional[typing.Callable[[path.File, SendMessage], None]]): Handler for other files.
    """

    handle_aps: typing.Optional[typing.Callable[[ApsFile, SendMessage], None]] = None
    handle_dvs: typing.Optional[typing.Callable[[DvsFile, SendMessage], None]] = None
    handle_imu: typing.Optional[typing.Callable[[ImuFile, SendMessage], None]] = None
    handle_other: typing.Optional[
        typing.Callable[[path.File, SendMessage], None]
    ] = None

    def enabled_types(self) -> set[typing.Any]:
        """Lists the file types that have a non-None handler.

        Returns:
            set[typing.Any]: The set of file classes that will be handled.
        """
        result = set()
        if self.handle_aps is not None:
            result.add(ApsFile)
        if self.handle_dvs is not None:
            result.add(DvsFile)
        if self.handle_imu is not None:
            result.add(ImuFile)
        return result

    def handle_file(self, file: path.File, send_message: SendMessage):
        """Calls the specialized file handler for the file, if the handler is non-None.

        Args:
            file (path.File): The file to process.
            send_message (SendMessage): Callback channel for messages.

        Raises:
            RuntimeError: if the file type is not supported by this function.
        """
        if self.handle_aps is not None and isinstance(file, ApsFile):
            self.handle_aps(file, send_message)
        elif self.handle_dvs is not None and isinstance(file, DvsFile):
            self.handle_dvs(file, send_message)
        elif self.handle_imu is not None and isinstance(file, ImuFile):
            self.handle_imu(file, send_message)
        elif self.handle_other is not None and file.__class__ == path.File:
            self.handle_other(file, send_message)
        else:
            raise RuntimeError(f"unsupported file format {file.__class__}")
