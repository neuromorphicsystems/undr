from __future__ import annotations

import contextlib
import dataclasses
import exception
import functools
import math
import operator
import pathlib
import typing

import requests

from . import constants, decode, remote, task, utilities

if typing.TYPE_CHECKING:
    from . import path_directory

try:
    functools.cached_property
except:
    functools.cached_property = property


class Download(remote.Download):
    """Downloads a remote file.

    This task is never used with a scheduler. Its run function is called by :py:meth:`File.chunks` to recycle the download logic implemented in py:class:`undr.remote.Download`.

    Args:
        path_id (pathlib.PurePosixPath): The resource's unique path id.
        suffix (typing.Optional[str]): Added to the file name while it is being downloaded.
        server (Server): The remote server.
        stream (bool): Whether to download the file in chunks (slightly slower for small files, reduces memory usage for large files).
    """

    def __init__(
        self,
        path_id: pathlib.PurePosixPath,
        suffix: typing.Optional[str],
        server: remote.Server,
        stream: bool,
    ):
        super().__init__(path_id=path_id, suffix=suffix, server=server, stream=stream)
        self.response: typing.Optional[requests.Response] = None

    def on_begin(self, manager: task.Manager) -> int:
        return 0

    def on_response_ready(self, response: requests.Response, manager: task.Manager):
        self.response = response


@dataclasses.dataclass(frozen=True)
class Path:
    """A file or directory in a dataset.

    A path can point to a local resource or represent a remote resource.
    """

    path_root: pathlib.Path
    """Path to the root "datasets" directory used to generate local paths.
    """

    path_id: pathlib.PurePosixPath
    """A POSIX path uniquely identifying the resource (including its dataset).
    """

    own_doi: typing.Optional[str] = dataclasses.field(compare=False, hash=False)
    """This resource's DOI, used by all its children unless they have their own DOI.
    """

    metadata: dict[str, typing.Any] = dataclasses.field(compare=False, hash=False)
    """Any data not strictly required to decode the file (stored in -index.json).
    """

    server: remote.Server = dataclasses.field(repr=False, compare=False, hash=False)
    """The resource's remote server, used to download data if it is not available locally.
    """

    @functools.cached_property
    def local_path(self) -> pathlib.Path:
        """Returns the local file path.

        This function always return a path, even if the local resource does not exist.

        Returns:
            pathlib.Path: The path to the local resource.
        """
        return self.path_root / self.path_id

    def __truediv__(self, other: str) -> "Path":
        """Concatenates this path with a string to create a new path.

        Args:
            other (str): Suffix to append to this path.

        Returns:
            Path: The concatenated result.
        """
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True)
class File(Path):
    """Represents a local or remote file."""

    size: int = dataclasses.field(compare=False, hash=False)
    """The decompressed file size in bytes.
    """

    hash: str = dataclasses.field(compare=False, hash=False)
    """The decompressed file hash (SHA3-224).
    """

    compressions: tuple[decode.Compression, ...] = dataclasses.field(
        repr=False, compare=False, hash=False
    )
    """List of compressions available on the server.
    """

    session: typing.Optional[requests.Session] = dataclasses.field(
        repr=False, compare=False, hash=False
    )
    """An open session that can be used to download resources.
    """

    manager: task.Manager = dataclasses.field(repr=False, compare=False, hash=False)
    """Can be called to schedule new tasks and report updates.
    """

    @functools.cached_property
    def best_compression(self) -> decode.Compression:
        """Returns the best compression supported by the remote server for this file.

        Best is defined here as "smallest encoded size".

        Returns:
            decode.Compression: Compression format that yields the smallest version of this file.
        """
        return min(self.compressions, key=operator.attrgetter("size"))

    @functools.cached_property
    def word_size(self) -> int:
        """The size of an entry in this file, in bytes.

        This can be used to ensure that entries (events, frames...) are not split while reading.
        A decoded file's size in bytes must be a multiple of the value returned by this function.

        Returns:
            int: Number of bytes used by each entry.
        """
        return 1

    @staticmethod
    def attributes_from_dict(
        data: dict[str, typing.Any], parent: "path_directory.Directory"
    ) -> dict[str, typing.Any]:
        """Converts -index.json data to a dict of this class's arguments.

        The returned dict can be used to initialise an instance of this class.

        Args:
            data (dict[str, typing.Any]): Parsed JSON data.
            parent (path_directory.Directory): The file's parent directory.

        Returns:
            dict[str, typing.Any]: Data that can be used to initialize this class.
        """
        return {
            "path_root": parent.path_root,
            "path_id": parent.path_id / data["name"],
            "own_doi": data["doi"] if "doi" in data else None,
            "metadata": data["metadata"],
            "server": parent.server,
            "size": data["size"],
            "hash": data["hash"],
            "compressions": tuple(
                decode.compression_from_dict(
                    data=compression,
                    base_size=data["size"],
                    base_hash=data["hash"],
                )
                for compression in data["compressions"]
            ),
            "session": None,
            "manager": task.NullManager(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any], parent: "path_directory.Directory"):
        """Conerts -index.json data to an instance of this class.

        Args:
            data (dict[str, typing.Any]): Parsed JSON data.
            parent (path_directory.Directory): The file's parent directory.

        Returns:
            File: The file represented by the given data.
        """
        return cls(**File.attributes_from_dict(data=data, parent=parent))

    def __truediv__(self, other: str) -> Path:
        raise Exception(f'the file path "{self.path_id}" cannot be extended')

    def _chunks(self, word_size: int) -> typing.Iterable[bytes]:
        """Returns an iterator over the file's decompressed bytes.

        Users should prefer :py:func:`chunks` since files know their word size.

        Args:
            word_size (int): size of an entry (events, frames...) in the file.

        Raises:
            decode.RemainingBytesError: if the total file size is not a multiple of `word_size`.
            Exception: if the hash is incorrect.

        Returns:
            typing.Iterable[bytes]: @DEV how to document iterators?

        Yields:
            Iterator[typing.Iterable[bytes]]: @DEV how to document iterators?
        """
        assert word_size > 0
        if self.local_path.is_file():
            hash = utilities.new_hash()
            chunk_size = math.ceil(65536 / word_size) * word_size
            with open(self.local_path, "rb") as file_object:
                while True:
                    chunk = file_object.read(chunk_size)
                    if len(chunk) == 0:
                        break
                    if len(chunk) % word_size != 0:
                        raise decode.RemainingBytesError(
                            word_size=word_size, buffer=chunk
                        )
                    yield chunk
                    hash.update(chunk)
                    self.manager.send_message(
                        decode.Progress(
                            path_id=self.path_id,
                            initial_bytes=0,
                            current_bytes=len(chunk),
                            final_bytes=len(chunk),
                            complete=False,
                        )
                    )
            digest = hash.hexdigest()
            if digest != self.hash:
                raise exception.HashMismatch(self.path_id, self.hash, digest)
            self.manager.send_message(
                decode.Progress(
                    path_id=self.path_id,
                    initial_bytes=0,
                    current_bytes=0,
                    final_bytes=0,
                    complete=True,
                )
            )
        elif utilities.path_with_suffix(
            self.local_path, self.best_compression.suffix
        ).is_file():
            hash = utilities.new_hash()
            with open(
                utilities.path_with_suffix(
                    self.local_path, self.best_compression.suffix
                ),
                "rb",
            ) as compressed_file:
                decoder = self.best_compression.decoder(self.word_size)
                while True:
                    encoded_bytes = compressed_file.read(constants.CHUNK_SIZE)
                    if len(encoded_bytes) == 0:
                        break
                    decoded_bytes = decoder.decompress(encoded_bytes)
                    yield decoded_bytes
                    hash.update(decoded_bytes)
                    self.manager.send_message(
                        decode.Progress(
                            path_id=self.path_id,
                            initial_bytes=0,
                            current_bytes=len(decoded_bytes),
                            final_bytes=len(decoded_bytes),
                            complete=False,
                        )
                    )
                decoded_bytes, remaining_bytes = decoder.finish()
                if len(decoded_bytes) > 0:
                    yield decoded_bytes
                    hash.update(decoded_bytes)
                    self.manager.send_message(
                        decode.Progress(
                            path_id=self.path_id,
                            initial_bytes=0,
                            current_bytes=len(decoded_bytes),
                            final_bytes=len(decoded_bytes),
                            complete=False,
                        )
                    )
                if len(remaining_bytes) > 0:
                    raise decode.RemainingBytesError(word_size, remaining_bytes)
            digest = hash.hexdigest()
            if digest != self.hash:
                raise exception.HashMismatch(self.path_id, self.hash, digest)
            self.manager.send_message(
                decode.Progress(
                    path_id=self.path_id,
                    initial_bytes=0,
                    current_bytes=0,
                    final_bytes=0,
                    complete=True,
                )
            )
        else:
            download_hash = utilities.new_hash()
            decode_hash = utilities.new_hash()
            with (
                requests.Session() if self.session is None else contextlib.nullcontext()
            ) as local_session:
                if self.session is None:
                    self.attach_session(local_session)
                    assert self.session is not None
                decoder = self.best_compression.decoder(self.word_size)
                # this task is created to re-use download logic but it is never scheduled
                # we call run directy below
                download = Download(
                    path_id=self.path_id,
                    suffix=self.best_compression.suffix,
                    server=self.server,
                    stream=self.size
                    >= constants.CHUNK_SIZE * constants.STREAM_CHUNK_THRESHOLD,
                )
                download.run(session=self.session, manager=self.manager)
                assert download.response is not None
                for encoded_bytes in download.response.iter_content(
                    constants.CHUNK_SIZE
                ):
                    download_hash.update(encoded_bytes)
                    self.manager.send_message(
                        remote.Progress(
                            path_id=self.path_id,
                            initial_bytes=0,
                            current_bytes=len(encoded_bytes),
                            final_bytes=len(encoded_bytes),
                            complete=False,
                        )
                    )
                    decoded_bytes = decoder.decompress(encoded_bytes)
                    yield decoded_bytes
                    decode_hash.update(decoded_bytes)
                    self.manager.send_message(
                        decode.Progress(
                            path_id=self.path_id,
                            initial_bytes=0,
                            current_bytes=len(decoded_bytes),
                            final_bytes=len(decoded_bytes),
                            complete=False,
                        )
                    )
                download.response.close()
            download_digest = download_hash.hexdigest()
            if download_digest != self.best_compression.hash:
                raise Exception(
                    f'bad download hash for "{self.path_id}" (expected "{self.best_compression.hash}", got "{download_digest}")'
                )
            self.manager.send_message(
                remote.Progress(
                    path_id=self.path_id,
                    initial_bytes=0,
                    current_bytes=0,
                    final_bytes=0,
                    complete=True,
                )
            )
            decoded_bytes, remaining_bytes = decoder.finish()
            if len(decoded_bytes) > 0:
                yield decoded_bytes
                decode_hash.update(decoded_bytes)
                self.manager.send_message(
                    decode.Progress(
                        path_id=self.path_id,
                        initial_bytes=0,
                        current_bytes=len(decoded_bytes),
                        final_bytes=len(decoded_bytes),
                        complete=False,
                    )
                )
            if len(remaining_bytes) > 0:
                raise decode.RemainingBytesError(word_size, remaining_bytes)
            decode_digest = decode_hash.hexdigest()
            if decode_digest != self.hash:
                raise Exception(
                    f'bad download hash for "{self.path_id}" (expected "{self.hash}", got "{decode_digest}")'
                )
            self.manager.send_message(
                decode.Progress(
                    path_id=self.path_id,
                    initial_bytes=0,
                    current_bytes=0,
                    final_bytes=0,
                    complete=True,
                )
            )

    def chunks(self) -> typing.Iterable[bytes]:
        """Returns an iterator over the file's decompressed bytes.

        Returns:
            typing.Iterable[bytes]: Iterator over the decompressed file's bytes. The size of the chunks may vary.
        """
        yield from self._chunks(word_size=1)

    def attach_session(self, session: typing.Optional[requests.Session]):
        """Binds a session to this file.

        The session is used for all subsequent downloads.

        Args:
            session (typing.Optional[requests.Session]): An open session to use for downloads.
        """
        self.__dict__["session"] = session

    def attach_manager(self, manager: typing.Optional[task.Manager]):
        """Binds a manager to this file.

        The file sends all subsequent updates (download and processing) to the manager.

        Args:
            manager (typing.Optional[task.Manager]): The manager to use to keep track of progress.
        """
        self.__dict__["manager"] = manager
