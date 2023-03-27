from __future__ import annotations

import contextlib
import dataclasses
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
    def __init__(
        self,
        path_id: pathlib.PurePosixPath,
        suffix: typing.Union[str, None],
        server: remote.Server,
        stream: bool,
    ):
        super().__init__(path_id=path_id, suffix=suffix, server=server, stream=stream)
        self.response: typing.Optional[requests.Response] = None

    def on_begin(self, manager: task.Manager) -> int:
        return 0

    def on_response_ready(
        self, response: requests.Response, manager: task.Manager
    ) -> None:
        self.response = response


@dataclasses.dataclass(frozen=True)
class Path:
    path_root: pathlib.Path
    path_id: pathlib.PurePosixPath
    own_doi: typing.Optional[str] = dataclasses.field(compare=False, hash=False)
    metadata: dict[str, typing.Any] = dataclasses.field(compare=False, hash=False)
    server: remote.Server = dataclasses.field(repr=False, compare=False, hash=False)

    @functools.cached_property
    def local_path(self) -> pathlib.Path:
        return self.path_root / self.path_id

    def __truediv__(self, other: str) -> "Path":
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True)
class File(Path):
    size: int = dataclasses.field(compare=False, hash=False)
    hash: str = dataclasses.field(compare=False, hash=False)
    compressions: tuple[decode.Compression, ...] = dataclasses.field(
        repr=False, compare=False, hash=False
    )
    session: typing.Optional[requests.Session] = dataclasses.field(
        repr=False, compare=False, hash=False
    )
    manager: task.Manager = dataclasses.field(repr=False, compare=False, hash=False)

    @functools.cached_property
    def best_compression(self) -> decode.Compression:
        return min(self.compressions, key=operator.attrgetter("size"))

    @functools.cached_property
    def word_size(self) -> int:
        return 1

    @staticmethod
    def attributes_from_dict(
        data: dict[str, typing.Any], parent: "path_directory.Directory"
    ):
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
        return cls(**File.attributes_from_dict(data=data, parent=parent))

    def __truediv__(self, other: str) -> Path:
        raise Exception(f'the file path "{self.path_id}" cannot be extended')

    def _chunks(self, word_size: int) -> typing.Iterable[bytes]:
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
                raise Exception(
                    f'bad hash for "{self.path_id}" (expected "{self.hash}", got "{digest}")'
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
                raise Exception(
                    f'bad hash for "{self.path_id}" (expected "{self.hash}", got "{digest}")'
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
        yield from self._chunks(word_size=1)

    def attach_session(self, session: typing.Optional[requests.Session]):
        self.__dict__["session"] = session

    def attach_manager(self, manager: typing.Optional[task.Manager]):
        self.__dict__["manager"] = manager
