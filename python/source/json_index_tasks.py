"""Implementation of operations based on index files (recursive download, recursive aaction dispatch...)."""

from __future__ import annotations

import dataclasses
import enum
import itertools
import logging
import pathlib
import typing

import requests

from . import (
    constants,
    decode,
    formats,
    json_index,
    path,
    path_directory,
    remote,
    task,
    utilities,
)


@dataclasses.dataclass
class IndexLoaded:
    """Message indicating that the given index file has been loaded."""

    path_id: pathlib.PurePosixPath
    """Path ID of the directory whose index has been loaded.
    """

    children: int
    """Number of subdirectories that will subsequently be loaded.
    """


@dataclasses.dataclass
class IndexProgress:
    """Represents download or process progress."""

    initial: int
    """Number of bytes already downloaded or processed when the action started.
    """

    final: int
    """Total number of bytes to download or process.
    """


@dataclasses.dataclass
class DirectoryScanned:
    """Reports information on a local directory."""

    path_id: pathlib.PurePosixPath
    """Path ID of the directory.
    """

    initial_download_count: int
    """Number of files already downloaded when the action started ("files" and "other_files").

    This count does not include -index.json.
    """

    initial_process_count: int
    """Number of files already processed when the action started ("files" and "other_files").

    This count does not include -index.json.
    """

    final_count: int  # does not include -index.json
    """Total number of files in this directory ("files" and "other_files").

    This count does not include -index.json.
    """

    index_bytes: IndexProgress
    """Size of the index file (-index.json) in bytes.
    """

    download_bytes: IndexProgress
    """Total size of the compressed files in this directory, in bytes.

    This size does not include -index.json.
    """

    process_bytes: IndexProgress
    """Total size of the files in this directory, in bytes.

    This size does not include -index.json.
    """


@dataclasses.dataclass
class Doi:
    """Message dispatched when a DOI is found in the index."""

    path_id: pathlib.PurePosixPath
    """Path ID of the associated resource.
    """

    value: str
    """Digital object identifier (DOI) string starting with ``10.``.
    """


class UncompressedDecodeProgress(task.Task):
    """Dummy task that repoorts progress on "decompression" for uncompressed resources.

    Resources that are not compressed are directly downloaded in raw format.
    The conversion from "local" to "raw" (decompression) requires no further action for such resources.
    This action dispatches decompression progress as if they were compressed, to simplify the architecture of progress trackers.
    """

    def __init__(self, path_id: pathlib.PurePosixPath, size: int):
        self.path_id = path_id
        self.size = size

    def run(self, session: requests.Session, manager: task.Manager):
        manager.send_message(
            decode.Progress(
                path_id=self.path_id,
                initial_bytes=0,
                current_bytes=self.size,
                final_bytes=0,
                complete=True,
            )
        )


class Selector:
    """Delegate called to pick an action for each file.

    Selectors are used during the indexing phase to calculate the number of bytes to download and/or process,
    and during the processing phase to choose the action to perform.
    """

    class Action(enum.Enum):
        """Specifies the operation to perform for a given file.

        The action also determines whether the file's bytes should be
        accounted for during the indexing phase.
        This is useful to report non-zero progress after resuming a job,
        but skip the actual processing.
        """

        IGNORE = 0
        """Skips this file and does not report it.
        """
        DOI = 1
        """Skips this file, does not report it, but publishes own DOIs.
        """
        SKIP = 2
        """Skips this file but reports it as downloaded and processed.
        """

        DOWNLOAD_SKIP = 3
        """Skips operations on this file but reports it as downloaded.
        """
        DOWNLOAD = 4
        """Downloads and reports.
        """
        DECOMPRESS = 5
        """Downloads, decompresses, and reports.
        """
        PROCESS = 6
        """Downloads, decompresses, processes, and reports.
        """

    SKIP_ACTIONS = {Action.SKIP, Action.DOWNLOAD_SKIP}
    """The set of actions that skip all operations on the file.
    """

    REPORT_DOWNLOAD_ACTIONS = {
        Action.SKIP,
        Action.DOWNLOAD_SKIP,
        Action.DOWNLOAD,
        Action.DECOMPRESS,
        Action.PROCESS,
    }
    """The set of actions that (at least) download the file.
    """

    REPORT_PROCESS_ACTIONS = {Action.SKIP, Action.DECOMPRESS, Action.PROCESS}
    """The set of actions that download and process the file.
    """

    INSTALL_IGNORE_ACTIONS = {
        Action.IGNORE,
        Action.DOI,
        Action.SKIP,
        Action.DOWNLOAD_SKIP,
    }
    """The set of actions that ignore the file for reporting purposes.
    """

    def action(self, file: path.File) -> "Selector.Action":
        """Returns the action to apply to the given file.

        Called by :py:class:`Index`, :py:class:`InstallFilesRecursive` and :py:class:`ProcessFilesRecursive`.
        The default implementation returns `Selector.Action.PROCESS`.
        """
        return Selector.Action.PROCESS

    def scan_filesystem(self, directory: path_directory.Directory) -> bool:
        """Whether to scan the filesystem.

        Called by :py:class:`Index` to decide whether it needs to scan the file system.
        This function may return False if :py:func:`action` returns one of the following for every file in the directory:

        - :py:attr:`Selector.Action.IGNORE`
        - :py:attr:`Selector.Action.DOI`
        - :py:attr:`Selector.Action.SKIP`
        - :py:attr:`Selector.Action.DOWNLOAD_SKIP`
        """
        return True


class Index(remote.DownloadFile):
    """Downloads an index file (-index.json).

    Args:
        path_root (pathlib.Path): The root path used to generate local file paths.
        path_id (pathlib.PurePosixPath): The path ID of the directory that will be seached recursively.
        server (remote.Server): The remote server to download resources.
        selector (Selector): A selector that defines the files to process.
        priority (int): Priority of this task (tasks with lower priorities are scheduled first).
        force (bool): Download the index file even if it is already present locally.
        directory_doi (bool): Whether to dispatch :py:class:`Doi` messages while reading the index.
    """

    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        server: remote.Server,
        selector: Selector,
        priority: int,
        force: bool,
        directory_doi: bool,
    ):
        self.index_file = path.File(
            path_root=path_root,
            path_id=path_id / "-index.json",
            own_doi=None,
            metadata={},
            server=server,
            # size, hash, and compressions are not available for index files
            # they are always non-null when path.File objects are exposed to the user via Selector,
            # so we keep the type as a non-optional
            size=None,  # type: ignore
            hash=None,  # type: ignore
            compressions=None,  # type: ignore
            session=None,
            manager=task.NullManager(),
        )
        super().__init__(
            path_root=path_root,
            path_id=path_id / "-index.json",
            suffix=None,
            server=server,
            force=force,
            expected_size=None,
            expected_hash=None,
        )
        self.selector = selector
        self.priority = priority
        self.directory_doi = directory_doi

    def run(self, session: requests.Session, manager: task.Manager):
        directory = path_directory.Directory(
            path_root=self.path_root,
            path_id=self.path_id.parent,
            own_doi=None,
            metadata={},
            server=self.server,
            doi_and_metadata_loaded=False,
        )
        directory.local_path.mkdir(exist_ok=True)
        directory_scanned = DirectoryScanned(
            path_id=directory.path_id,
            initial_download_count=0,
            initial_process_count=0,
            final_count=0,
            index_bytes=IndexProgress(initial=0, final=0),
            download_bytes=IndexProgress(initial=0, final=0),
            process_bytes=IndexProgress(initial=0, final=0),
        )
        if not self.force:
            if self.index_file.local_path.is_file():
                directory_scanned.index_bytes.initial = (
                    self.index_file.local_path.stat().st_size
                )
            else:
                partial_index_path = utilities.path_with_suffix(
                    self.path_root / self.path_id, constants.DOWNLOAD_SUFFIX
                )
                if partial_index_path.is_file():
                    directory_scanned.index_bytes.initial = (
                        partial_index_path.stat().st_size
                    )
        super().run(session=session, manager=manager)
        index_data = json_index.load(self.path_root / self.path_id)
        if "doi" in index_data:
            directory.__dict__["own_doi"] = index_data["doi"]
        if "metadata" in index_data:
            directory.__dict__["metadata"] = index_data["metadata"]
        manager.send_message(
            IndexLoaded(
                path_id=directory.path_id,
                children=len(index_data["directories"]),
            )
        )
        for child_directory_name in index_data["directories"]:
            manager.schedule(
                Index(
                    path_root=self.path_root,
                    path_id=directory.path_id / child_directory_name,
                    server=self.server,
                    selector=self.selector,
                    priority=self.priority,
                    force=self.force,
                    directory_doi=self.directory_doi,
                ),
                priority=self.priority,
            )
        if self.selector.scan_filesystem(directory=directory):
            name_to_size = {
                path.name: path.stat().st_size
                for path in directory.local_path.iterdir()
            }
        else:
            name_to_size = {"-index.json": self.index_file.local_path.stat().st_size}
        directory_scanned.index_bytes.final = name_to_size["-index.json"]
        if self.directory_doi:
            if directory.own_doi is not None:
                manager.send_message(
                    Doi(path_id=directory.path_id, value=directory.own_doi)
                )
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
            action = self.selector.action(file)
            if action == Selector.Action.IGNORE:
                continue
            if action == Selector.Action.DOI:
                if file.own_doi is not None:
                    manager.send_message(Doi(path_id=file.path_id, value=file.own_doi))
                continue
            directory_scanned.final_count += 1
            if action in Selector.REPORT_DOWNLOAD_ACTIONS:
                directory_scanned.download_bytes.final += file.best_compression.size
                if action in Selector.REPORT_PROCESS_ACTIONS:
                    directory_scanned.process_bytes.final += file.size
                if action in Selector.SKIP_ACTIONS:
                    directory_scanned.initial_download_count += 1
                    directory_scanned.download_bytes.initial += (
                        file.best_compression.size
                    )
                    if action in Selector.REPORT_PROCESS_ACTIONS:
                        directory_scanned.initial_process_count += 1
                        directory_scanned.process_bytes.initial += file.size
                elif not self.force:
                    if file.path_id.name in name_to_size:
                        directory_scanned.initial_download_count += 1
                        directory_scanned.download_bytes.initial += (
                            file.best_compression.size
                        )
                        if action in Selector.REPORT_PROCESS_ACTIONS:
                            directory_scanned.initial_process_count += 1
                            directory_scanned.process_bytes.initial += file.size
                    else:
                        compressed_name = (
                            f"{file.path_id.name}{file.best_compression.suffix}"
                        )
                        if compressed_name in name_to_size:
                            directory_scanned.initial_download_count += 1
                            directory_scanned.download_bytes.initial += (
                                file.best_compression.size
                            )
                        else:
                            partial_compressed_name = (
                                f"{compressed_name}{constants.DOWNLOAD_SUFFIX}"
                            )
                            if (
                                # in process mode, files are not persisted to the disk
                                # data is downloaded (or read from the disk), decompressed if necessaary,
                                # and processed in chunks
                                # for simplicity, partially persisted downloads are ignored and re-downloaded from scratch
                                action != Selector.Action.PROCESS
                                and partial_compressed_name in name_to_size
                            ):
                                directory_scanned.download_bytes.initial += (
                                    name_to_size[partial_compressed_name]
                                )
        manager.send_message(directory_scanned)


class InstallFilesRecursive(task.Task):
    """Downloads (and possibly decompresses) a directories' files recursively.

    The actual action is controlledd by the selector aand may be different for different files. Child directories are installed recursively.

    Args:
        path_root (pathlib.Path): The root path used to generate local file paths.
        path_id (pathlib.PurePosixPath): The path ID of the directory that will be seached recursively.
        server (remote.Server): The remote server to download resources.
        selector (Selector): A selector that defines the files to process.
        priority (int): Priority of this task (tasks with lower priorities are scheduled first).
        force (bool): Download files even if they already present locally.
    """

    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        server: remote.Server,
        selector: Selector,
        priority: int,
        force: bool,
    ):
        self.path_root = path_root
        self.path_id = path_id
        self.server = server
        self.selector = selector
        self.priority = priority
        self.force = force

    def run(self, session: requests.Session, manager: task.Manager):
        directory = path_directory.Directory(
            path_root=self.path_root,
            path_id=self.path_id,
            own_doi=None,
            metadata={},
            server=self.server,
            doi_and_metadata_loaded=False,
        )
        index_data = json_index.load(directory.local_path / "-index.json")
        if self.selector.scan_filesystem(directory=directory):
            names = set(path.name for path in directory.local_path.iterdir())
        else:
            names: set[str] = set()
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
            file.attach_session(session)
            file.attach_manager(manager)
            action = self.selector.action(file)
            if action in Selector.INSTALL_IGNORE_ACTIONS:
                continue
            if (
                not self.force
                and action == Selector.Action.PROCESS
                and not file.path_id.name in names
                and not f"{file.path_id.name}{file.best_compression.suffix}" in names
                and f"{file.path_id.name}{file.best_compression.suffix}{constants.DOWNLOAD_SUFFIX}"
                in names
            ):
                utilities.path_with_suffix(
                    file.local_path,
                    f"{file.best_compression.suffix}{constants.DOWNLOAD_SUFFIX}",
                ).unlink()
            # 0: skip
            # 1: download
            # 2: download and publish decompress progress when done (uncompressed file)
            # 3: download and decompress
            # 4: decompress
            actual_action: int = 0
            if self.force:
                if action == Selector.Action.DOWNLOAD:
                    actual_action = 1
                elif isinstance(file.best_compression, decode.NoneCompression):
                    actual_action = 2
                else:
                    actual_action = 3
            elif file.path_id.name in names:
                actual_action = 0
            elif action == Selector.Action.DOWNLOAD:
                if f"{file.path_id.name}{file.best_compression.suffix}" in names:
                    actual_action = 0
                else:
                    actual_action = 1
            elif isinstance(file.best_compression, decode.NoneCompression):
                actual_action = 2
            else:
                if f"{file.path_id.name}{file.best_compression.suffix}" in names:
                    actual_action = 4
                else:
                    actual_action = 3
            logging.debug(
                f"path_id={file.path_id} force={self.force} {action=} {actual_action=}"
            )
            if actual_action != 0:
                download_task = remote.DownloadFile(
                    path_root=self.path_root,
                    path_id=file.path_id,
                    suffix=file.best_compression.suffix,
                    server=self.server,
                    force=self.force,
                    expected_size=file.best_compression.size,
                    expected_hash=file.best_compression.hash,
                )
                decompress_task = decode.DecompressFile(
                    path_root=self.path_root,
                    path_id=file.path_id,
                    compression=file.best_compression,
                    expected_size=file.size,
                    expected_hash=file.hash,
                    word_size=file.word_size,
                    keep=False,
                )
                if actual_action == 1:
                    manager.schedule(download_task, self.priority)
                elif actual_action == 2:
                    manager.schedule(
                        task.Chain(
                            (
                                download_task,
                                UncompressedDecodeProgress(
                                    path_id=file.path_id,
                                    size=file.size,
                                ),
                            )
                        ),
                        self.priority,
                    )
                elif actual_action == 3:
                    manager.schedule(
                        task.Chain((download_task, decompress_task)), self.priority
                    )
                elif actual_action == 4:
                    manager.schedule(decompress_task, self.priority)
                else:
                    raise Exception(f"unexpected action {actual_action}")
        for child_directory_name in index_data["directories"]:
            manager.schedule(
                InstallFilesRecursive(
                    path_root=self.path_root,
                    path_id=self.path_id / child_directory_name,
                    server=self.server,
                    selector=self.selector,
                    priority=self.priority,
                    force=self.force,
                ),
                priority=self.priority,
            )


class ProcessFile(task.Task):
    """Generic task for file processing.

    Args:
        file (path.File): The file (remote or local) to process.
    """

    def __init__(self, file: path.File):
        self.file = file


ProcessFileType = typing.TypeVar("ProcessFileType", bound=ProcessFile)
"""Generic parameter representing the file type.

Used by :py:class:`ProcessFilesRecursive`.
"""


class ProcessFilesRecursive(task.Task):
    """Spawns a processing task for each file in the given directory.

    Subdirectories are recursively searched as well.

    Args:
        path_root (pathlib.Path): The root path used to generate local file paths.
        path_id (pathlib.PurePosixPath): The path ID of the directory that will be scanned recursively.
        server (remote.Server): The remote server used to download resources.
        selector (Selector): A selector that defines the files to process.
        process_file_class (typing.Type[ProcessFileType]): The class of the task to run on each selected file. Must be a subclass of :py:class:`ProcessFile`.
        process_file_args (typing.Iterable[typing.Any]): Positional arguments passed to the constructor of `process_file_class`.
        process_file_kwargs (typing.Mapping[str, typing.Any]): Keyword arguments passed to the constructor of `process_file_class`. The keyword argument `file` is automatically added by `ProcessFilesRecursive` after the positional arguments and before other keyword arguments.
        priority (int): Priority of this task and all recursively created tasks (tasks with lower priorities are scheduled first).
    """

    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        server: remote.Server,
        selector: Selector,
        process_file_class: typing.Type[ProcessFileType],
        process_file_args: typing.Iterable[typing.Any],
        process_file_kwargs: typing.Mapping[str, typing.Any],
        priority: int,
    ):
        self.path_root = path_root
        self.path_id = path_id
        self.server = server
        self.process_file_class = process_file_class
        self.process_file_args = process_file_args
        self.process_file_kwargs = process_file_kwargs
        self.selector = selector
        self.priority = priority

    def run(self, session: requests.Session, manager: task.Manager) -> None:
        directory = path_directory.Directory(
            path_root=self.path_root,
            path_id=self.path_id,
            own_doi=None,
            metadata={},
            server=self.server,
            doi_and_metadata_loaded=False,
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
            action = self.selector.action(file)
            if action == Selector.Action.PROCESS:
                manager.schedule(
                    task=self.process_file_class(
                        *self.process_file_args,
                        file=file,
                        **self.process_file_kwargs,
                    ),
                    priority=self.priority,
                )
        for child_directory_name in index_data["directories"]:
            manager.schedule(
                ProcessFilesRecursive(
                    path_root=self.path_root,
                    path_id=self.path_id / child_directory_name,
                    server=self.server,
                    selector=self.selector,
                    process_file_class=self.process_file_class,
                    process_file_args=self.process_file_args,
                    process_file_kwargs=self.process_file_kwargs,
                    priority=self.priority,
                ),
                priority=self.priority,
            )
