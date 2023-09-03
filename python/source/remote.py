"""Low-level implementation of resource download."""

from __future__ import annotations

import dataclasses
import exception
import hashlib
import io
import pathlib
import typing

import requests

from . import constants, task, utilities


@dataclasses.dataclass
class Progress:
    """Message that reports download progress."""

    path_id: pathlib.PurePosixPath
    """Path ID of the associated resource
    """

    initial_bytes: int
    """Number of bytes of the remote resource that were already downloaded when the current download began.
    """

    current_bytes: int
    """Number of bytes of the remote resource that have been downloaded so far.
    """

    final_bytes: int
    """Total number of bytes of the remote resource.
    """

    complete: bool
    """Whether this resource has been completely downloaded.
    """


@dataclasses.dataclass(frozen=True)
class Server:
    """Represents a remote server."""

    url: str
    """The server's base URL.

    Resources URL are calculated by appending the file's path ID to the server URL. A slash is inserted before the path ID if the server's URL does not end with one.
    """

    timeout: float
    """Timeout in seconds for requests to this server.
    """

    def path_id_to_url(self, path_id: pathlib.PurePosixPath) -> str:
        """Calculates a resource URL from its path ID.

        Args:
            path_id (pathlib.PurePosixPath): The resource's path ID, including the dataset name.

        Returns:
            str: The resource's remote URL.
        """
        if len(path_id.parts) == 1:
            return self.url
        return "{}{}{}".format(
            self.url,
            "" if self.url.endswith("/") else "/",
            "/".join(path_id.parts[1:]),
        )


@dataclasses.dataclass(frozen=True)
class NullServer(Server):
    """A placeholder server that raises an exception when used.

    Some functions and classes require a server to download resources that are no available locally.
    If the resources are known to be local, this server can be used to detect download attempts.
    """

    def __init__(self):
        super().__init__(url="", timeout=0.0)

    def path_id_to_url(self, path_id: pathlib.PurePosixPath):
        raise NotImplementedError()


class Download(task.Task):
    """Retrieves data from a remote server.

    This is an abstract task that calls its methods (lifecycle callbacks) as follows:

    - :py:meth:`on_begin` is called before contacting the server.
      This function can be used to create write resources and must return an offset in bytes.
      Download resumes from that offset if it is non-zero.
      If the offset is negative, the task assumes that the download is complete and it calls :py:meth:`on_end` immediately.
    - :py:meth:`on_range_failed` is called if :py:meth:`on_begin` returned a non-zero offset and the server
      rejects the range request (HTTP 206). It can be used to clean up 'append' resources and replace them
      with 'write' resources. The actual download starts after :py:meth:`on_range_failed` as if :py:meth:`on_begin` returned 0.
    - :py:meth:`on_response_ready` is called when the response is ready for iteration.
      The subclass must call :py:meth:`requests.Response.close` after reading the response (and probably :py:meth:`on_end`).

    This lifecycle allows users to yield on response chunks (see :py:meth:`undr.path.File._chunks` for an example).

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
        server: Server,
        stream: bool,
    ):
        self.path_id = path_id
        self.suffix = suffix
        self.server = server
        self.stream = stream

    def url(self) -> str:
        """Returns the file's remote URL.

        Returns:
            str: File URL on the server.
        """
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
        """Called before contacting the server.

        This function must return an offset in bytes.

        - 0 indicates that the file is not downloaded yet.
        - Positive values indicate the number of bytes already downloaded.
        - Negative values indicate that the download is already complete and must be skipped.

        Args:
            manager (task.Manager): The task manager for reporting updates.

        Returns:
            int: Number of bytes already downloaded.
        """
        raise NotImplementedError()

    def on_range_failed(self, manager: task.Manager) -> None:
        """Called if the HTTP range call fails.

        The HTTP range request asks the serve to resumes download at
        a given byte offset. It used when :py:meth:`on_begin` returns a non-zero value.
        Range is not always supported by the server. This function should reset counters
        and ready the local file system for a standard (full) download.

        Args:
            manager (task.Manager): The task manager for reporting updates.
        """
        raise NotImplementedError()

    def on_response_ready(
        self, response: requests.Response, manager: task.Manager
    ) -> None:
        """Called when the HTTP response object is ready.

        The reponse object can be used to download the remote file.

        Args:
            response (requests.Response): HTTP response object.
            manager (task.Manager): The task manager for reporting updates.
        """
        raise NotImplementedError()

    def on_end(self, manager: task.Manager) -> None:
        """Called when the download task completes.

        This function is called automatically if the byte offset
        returned by :py:meth:`on_begin` is nagative.
        Implementations should call it after consuming the response in :py:meth:`on_response_ready`.

        Args:
            manager (task.Manager): The task manager for reporting updates.
        """
        raise NotImplementedError()


class DownloadFile(Download):
    """Retrieves data from a remote server and saves it to a file."""

    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        suffix: typing.Optional[str],
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

    def on_begin(self, manager: task.Manager) -> int:
        """Opens the local file before starting the download.

        If the file exists, this function opens it in append mode
        and returns its size in bytes.

        Args:
            manager (task.Manager): The task manager for reporting updates.

        Returns:
            int: Number of bytes already downloaded.
        """
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
        """Re-opens the file in write mode.

        Args:
            manager (task.Manager): The task manager for reporting updates.
        """
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
        """Iterates over the file chunks and writes them to the file.

        Args:
            response (requests.Response): HTTP response object.
            manager (task.Manager): The task manager for reporting updates.
        """
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
        """Checks the hash and closes the file.

        Args:
            manager (task.Manager): The task manager for reporting updates.

        Raises:
            exception.HashMismatch: if the provided and effective hashes are different.
            exception.SizeMismatch: if the provided and effective sizes are different.
        """
        if self.stream is not None:
            self.stream.close()
            if self.hash is not None:
                assert self.expected_hash is not None
                hash = self.hash.hexdigest()
                if hash != self.expected_hash:
                    raise exception.HashMismatch(self.path_id, self.expected_hash, hash)
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
                    raise exception.SizeMismatch(self.path_id, self.expected_size, size)
            download_path.replace(file_path)
            manager.send_message(
                Progress(
                    path_id=self.path_id,
                    initial_bytes=0,
                    current_bytes=0,
                    final_bytes=0,
                    complete=True,
                )
            )
