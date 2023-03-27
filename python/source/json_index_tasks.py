from __future__ import annotations

import dataclasses
import enum
import itertools
import logging
import pathlib
import typing

import requests

from . import (
    check,
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
    path_id: pathlib.PurePosixPath
    children: int


@dataclasses.dataclass
class Value:
    initial: int
    final: int


@dataclasses.dataclass
class DirectoryScanned:
    path_id: pathlib.PurePosixPath
    initial_download_count: int  # does not include -index.json
    initial_process_count: int  # does not include -index.json
    final_count: int  # does not include -index.json
    index_bytes: Value
    download_bytes: Value
    process_bytes: Value


@dataclasses.dataclass
class Doi:
    path_id: pathlib.PurePosixPath
    value: str


class UncompressedDecodeProgress(task.Task):
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
    class Action(enum.Enum):
        IGNORE = 0  # skip this file and do not report it
        DOI = 1  # skip this file, do not report it but publish own DOIs
        SKIP = 2  # skip this file but report it as downloaded and processed
        DOWNLOAD_SKIP = 3  # skip operations on this file but report it as downloaded
        DOWNLOAD = 4  # download only
        DECOMPRESS = 5  # download and decompress
        PROCESS = 6  # download, decompress, and process all bytes

    SKIP_ACTIONS = {Action.SKIP, Action.DOWNLOAD_SKIP}
    REPORT_DOWNLOAD_ACTIONS = {
        Action.SKIP,
        Action.DOWNLOAD_SKIP,
        Action.DOWNLOAD,
        Action.DECOMPRESS,
        Action.PROCESS,
    }
    REPORT_PROCESS_ACTIONS = {Action.SKIP, Action.DECOMPRESS, Action.PROCESS}
    INSTALL_IGNORE_ACTIONS = {
        Action.IGNORE,
        Action.DOI,
        Action.SKIP,
        Action.DOWNLOAD_SKIP,
    }

    def action(self, file: path.File) -> "Selector.Action":
        """
        Called by Index, InstallFilesRecursive and ProcessFilesRecursive to select the files to process.
        """
        return Selector.Action.PROCESS

    def scan_filesystem(self, directory: path_directory.Directory) -> bool:
        """
        Called by Index to decide whether it needs to scan the file system.
        `directory_scan` may return False if action returns one of the following
        for every file in `directory`:
        - Selector.Action.IGNORE
        - Selector.Action.DOI
        - Selector.Action.SKIP
        - Selector.Action.DOWNLOAD_SKIP
        """
        return True


class Index(remote.DownloadFile):
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
            index_bytes=Value(initial=0, final=0),
            download_bytes=Value(initial=0, final=0),
            process_bytes=Value(initial=0, final=0),
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
    def __init__(self, file: path.File):
        self.file = file


ProcessFileType = typing.TypeVar("ProcessFileType", bound=ProcessFile)


class ProcessFilesRecursive(task.Task):
    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        server: remote.Server,
        selector: Selector,
        process_file_class: typing.Type[ProcessFileType],
        process_file_args: typing.Iterable[typing.Any],
        # ProcessFilesRecursive automatically adds the keyword argument 'file' before kwds
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


class CheckFile(task.Task):
    def __init__(self, file: path.File, switch: formats.Switch):
        self.file = file
        self.switch = switch

    def run(self, session: requests.Session, manager: task.Manager):
        self.file.attach_session(session)
        self.file.attach_manager(manager)
        self.switch.handle_file(
            file=self.file,
            send_message=lambda message: manager.send_message(
                check.Error(path_id=self.file.path_id, message=message)
            ),
        )


class CheckLocalDirectoryRecursive(task.Task):
    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        switch: formats.Switch,
        priority: int,
    ):
        self.path_root = path_root
        self.path_id = path_id
        self.switch = switch
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
        check.handle_directory(
            directory=directory,
            send_message=lambda message: manager.send_message(
                check.Error(path_id=directory.path_id, message=message)
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
                    switch=self.switch,
                ),
                priority=self.priority,
            )
        for child_directory_name in index_data["directories"]:
            manager.schedule(
                CheckLocalDirectoryRecursive(
                    path_root=self.path_root,
                    path_id=self.path_id / child_directory_name,
                    switch=self.switch,
                    priority=self.priority,
                ),
                priority=self.priority,
            )
