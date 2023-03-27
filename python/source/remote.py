from __future__ import annotations

import dataclasses
import hashlib
import io
import pathlib
import typing

import requests

from . import constants, task, utilities


@dataclasses.dataclass
class Progress:
    path_id: pathlib.PurePosixPath
    initial_bytes: int
    current_bytes: int
    final_bytes: int
    complete: bool


@dataclasses.dataclass(frozen=True)
class Server:
    url: str
    timeout: float

    def path_id_to_url(self, path_id: pathlib.PurePosixPath):
        if len(path_id.parts) == 1:
            return self.url
        return "{}{}{}".format(
            self.url,
            "" if self.url.endswith("/") else "/",
            "/".join(path_id.parts[1:]),
        )


@dataclasses.dataclass(frozen=True)
class NullServer(Server):
    def __init__(self):
        super().__init__(url="", timeout=0.0)

    def path_id_to_url(self, path_id: pathlib.PurePosixPath):
        raise NotImplementedError()


class Download(task.Task):
    """
    This task downloads a file from a server, calling lifecycle callbacks as follows:
    - on_begin is called before contacting the server. It can be used to create write
        resources and must return an offset in bytes. Download resumes from that offset if it is non-zero.
        If the offset is negative, the task assumes the download is complete and it calls on_end immediately.
    - on_range_failed is called if on_begin returned a non-zero offset AND if the server
        rejects the range request (HTTP 206). It can be used to clean up 'append' resources and replace them
        with 'write' resources. The actual download starts after on_range_failed as if on_begin returned 0.
    - on_response_ready is called when the response is ready for iteration. The subclass MUST call response.close()
        after reading the response (and pprobably self.on_end(manager=manager)).
    This odd but flexible lifecycle lets users yield on response chunks (see path for an example).
    """

    def __init__(
        self,
        path_id: pathlib.PurePosixPath,
        suffix: typing.Union[str, None],
        server: Server,
        stream: bool,
    ):
        self.path_id = path_id
        self.suffix = suffix
        self.server = server
        self.stream = stream

    def url(self):
        return self.server.path_id_to_url(
            self.path_id
            if self.suffix is None
            else utilities.posix_path_with_suffix(self.path_id, self.suffix)
        )

    def run(self, session: requests.Session, manager: task.Manager):
        skip = self.on_begin(manager=manager)
        if skip < 0:
            self.on_end(manager=manager)
        else:
            response: typing.Optional[requests.Response] = None
            if skip > 0:
                response = session.get(
                    self.url(),
                    timeout=self.server.timeout,
                    stream=self.stream,
                    headers={"Range": f"bytes={skip}-"},
                )
                if response.status_code != 206:
                    self.on_range_failed(manager=manager)
                    response = None
            if response is None:
                response = session.get(
                    self.url(),
                    timeout=self.server.timeout,
                    stream=self.stream,
                )
            response.raise_for_status()
            self.on_response_ready(response=response, manager=manager)

    def on_begin(self, manager: task.Manager) -> int:
        raise NotImplementedError()

    def on_range_failed(self, manager: task.Manager) -> None:
        raise NotImplementedError()

    def on_response_ready(
        self, response: requests.Response, manager: task.Manager
    ) -> None:
        raise NotImplementedError()

    def on_end(self, manager: task.Manager) -> None:
        raise NotImplementedError()


class DownloadFile(Download):
    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        suffix: typing.Union[str, None],
        server: Server,
        force: bool,
        expected_size: typing.Optional[int],
        expected_hash: typing.Optional[str],
    ):
        super().__init__(
            path_id=path_id,
            suffix=suffix,
            server=server,
            stream=expected_size is None
            or expected_size >= constants.CHUNK_SIZE * constants.STREAM_CHUNK_THRESHOLD,
        )
        self.path_root = path_root
        self.force = force
        self.expected_size = expected_size
        self.expected_hash = expected_hash
        self.stream: typing.Optional[io.BufferedWriter] = None
        self.hash: typing.Optional["hashlib._Hash"] = None

    def on_begin(self, manager: task.Manager):
        file_path = (
            self.path_root / self.path_id
            if self.suffix is None
            else utilities.path_with_suffix(self.path_root / self.path_id, self.suffix)
        )
        download_path = utilities.path_with_suffix(file_path, constants.DOWNLOAD_SUFFIX)
        if self.force:
            self.stream = open(download_path, "wb")
            if self.expected_hash is not None:
                self.hash = utilities.new_hash()
            return 0
        if file_path.is_file():
            size = (
                file_path.stat().st_size
                if self.expected_size is None
                else self.expected_size
            )
            manager.send_message(
                Progress(
                    path_id=self.path_id,
                    initial_bytes=size,
                    current_bytes=size,
                    final_bytes=size,
                    complete=True,
                )
            )
            return -1
        if download_path.is_file():
            if self.expected_hash is not None:
                self.hash = utilities.hash_file(
                    path=download_path, chunk_size=constants.CHUNK_SIZE
                )
            self.stream = open(download_path, "ab")
            size = download_path.stat().st_size
            manager.send_message(
                Progress(
                    path_id=self.path_id,
                    initial_bytes=size,
                    current_bytes=size,
                    final_bytes=size,
                    complete=False,
                )
            )
            return size
        self.stream = open(download_path, "wb")
        if self.expected_hash is not None:
            self.hash = utilities.new_hash()
        return 0

    def on_range_failed(self, manager: task.Manager):
        assert self.stream is not None
        self.stream.close()
        file_path = (
            self.path_root / self.path_id
            if self.suffix is None
            else utilities.path_with_suffix(self.path_root / self.path_id, self.suffix)
        )
        download_path = utilities.path_with_suffix(file_path, constants.DOWNLOAD_SUFFIX)
        size = download_path.stat().st_size
        manager.send_message(
            Progress(
                path_id=self.path_id,
                initial_bytes=-size,
                current_bytes=-size,
                final_bytes=-size,
                complete=False,
            )
        )
        self.stream = open(download_path, "wb")
        if self.expected_hash is not None:
            self.hash = utilities.new_hash()

    def on_response_ready(
        self, response: requests.Response, manager: task.Manager
    ) -> None:
        assert self.stream is not None
        for chunk in response.iter_content(constants.CHUNK_SIZE):
            self.stream.write(chunk)
            if self.hash is not None:
                self.hash.update(chunk)
            size = len(chunk)
            manager.send_message(
                Progress(
                    path_id=self.path_id,
                    initial_bytes=0,
                    current_bytes=size,
                    final_bytes=size,
                    complete=False,
                )
            )
        response.close()
        self.on_end(manager=manager)

    def on_end(self, manager: task.Manager):
        if self.stream is not None:
            self.stream.close()
            if self.hash is not None:
                hash = self.hash.hexdigest()
                if hash != self.expected_hash:
                    raise Exception(
                        f'bad hash for "{self.path_id}" (expected "{self.expected_hash}", got "{hash}")'
                    )
            file_path = (
                self.path_root / self.path_id
                if self.suffix is None
                else utilities.path_with_suffix(
                    self.path_root / self.path_id, self.suffix
                )
            )
            download_path = utilities.path_with_suffix(
                file_path, constants.DOWNLOAD_SUFFIX
            )
            if self.expected_size is not None:
                size = download_path.stat().st_size
                if size != self.expected_size:
                    raise Exception(
                        f'bad size for "{self.path_id}" (expected "{self.expected_size}", got "{size}")'
                    )
            download_path.rename(file_path)
            manager.send_message(
                Progress(
                    path_id=self.path_id,
                    initial_bytes=0,
                    current_bytes=0,
                    final_bytes=0,
                    complete=True,
                )
            )
