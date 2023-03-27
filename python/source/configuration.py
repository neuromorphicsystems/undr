from __future__ import annotations

import contextlib
import dataclasses
import logging
import multiprocessing
import os
import pathlib
import typing

import requests
import toml

from . import (
    bibtex,
    constants,
    display,
    formats,
    install_mode,
    json_index,
    json_index_tasks,
    path,
    path_directory,
    persist,
    remote,
    task,
    utilities,
)

schema = utilities.load_schema("undr_schema.json")


class InstallSelector(json_index_tasks.Selector):
    def __init__(self, mode: install_mode.Mode):
        self.scan = False
        if mode == install_mode.Mode.REMOTE:
            self.cached_action = json_index_tasks.Selector.Action.IGNORE
        elif mode == install_mode.Mode.LOCAL:
            self.cached_action = json_index_tasks.Selector.Action.DOWNLOAD
            self.scan = True
        elif mode == install_mode.Mode.RAW:
            self.cached_action = json_index_tasks.Selector.Action.DECOMPRESS
            self.scan = True
        else:
            raise Exception(f'unexpected mode "{mode}"')

    def action(self, file: path.File) -> json_index_tasks.Selector.Action:
        return self.cached_action

    def scan_filesystem(self, directory: path_directory.Directory):
        return self.scan


class DoiSelector(json_index_tasks.Selector):
    def action(self, file: path.File) -> json_index_tasks.Selector.Action:
        return json_index_tasks.Selector.Action.DOI

    def scan_filesystem(self, directory: path_directory.Directory):
        return False


@dataclasses.dataclass
class DatasetSettings:
    name: str
    url: str
    mode: install_mode.Mode
    timeout: typing.Optional[float]


@dataclasses.dataclass
class IndexStatus:
    dataset_settings: DatasetSettings
    current_index_files: int
    final_index_files: int
    server: remote.Server
    selector: json_index_tasks.Selector
    downloaded_and_processed: bool

    def push(self, message: typing.Any) -> tuple[bool, typing.Optional["IndexStatus"]]:
        if isinstance(message, json_index_tasks.IndexLoaded):
            self.final_index_files += message.children
            return (False, self)
        if isinstance(message, json_index_tasks.DirectoryScanned):
            self.current_index_files += 1
            if (
                message.download_bytes.initial != message.download_bytes.final
                or message.process_bytes.initial != message.process_bytes.final
            ):
                self.downloaded_and_processed = False
            return (self.current_index_files == self.final_index_files, self)
        return False, None


@dataclasses.dataclass
class IndexesStatuses:
    name_to_status: dict[str, IndexStatus]

    def push(self, message: typing.Any) -> tuple[bool, typing.Optional[IndexStatus]]:
        """
        Updates the indexing status and returns it if message is an IndexLoaded or DirectoryScanned object.
        If the message was the last indexing message for this dataset, the first argument is True.
        """
        if isinstance(
            message, (json_index_tasks.IndexLoaded, json_index_tasks.DirectoryScanned)
        ):
            return self.name_to_status[message.path_id.parts[0]].push(message=message)
        return False, None


@dataclasses.dataclass
class MapMessage:
    payload: typing.Any


class MapSelector(json_index_tasks.Selector):
    def __init__(
        self,
        enabled_types: set[typing.Any],
        store: typing.Optional[persist.ReadOnlyStore],
    ):
        self.enabled_types = enabled_types
        self.store = store

    def action(self, file: path.File):
        if file.__class__ in self.enabled_types:
            if self.store is not None and str(file.path_id) in self.store:
                return json_index_tasks.Selector.Action.SKIP
            return json_index_tasks.Selector.Action.PROCESS
        return json_index_tasks.Selector.Action.IGNORE

    def scan_filesystem(self, directory: path_directory.Directory):
        return len(self.enabled_types) > 0


class MapProcessFile(json_index_tasks.ProcessFile):
    def __init__(self, file: path.File, switch: formats.Switch):
        super().__init__(file=file)
        self.switch = switch

    def run(self, session: requests.Session, manager: task.Manager):
        self.file.attach_session(session)
        self.file.attach_manager(manager)
        self.switch.handle_file(
            file=self.file,
            send_message=lambda message: manager.send_message(
                MapMessage(payload=message)
            ),
        )
        manager.send_message(persist.Progress(path_id=self.file.path_id))


@dataclasses.dataclass
class Configuration:
    directory: pathlib.Path
    name_to_dataset_settings: dict[str, DatasetSettings]

    def dataset(self, name: str) -> path_directory.Directory:
        dataset_settings = self.name_to_dataset_settings[name]
        if dataset_settings.mode == install_mode.Mode.DISABLED:
            raise Exception(f'"{name}" is disabled')
        return path_directory.Directory(
            path_root=self.directory,
            path_id=pathlib.PurePosixPath(dataset_settings.name),
            own_doi=None,
            metadata={},
            server=remote.Server(
                url=dataset_settings.url,
                timeout=constants.DEFAULT_TIMEOUT
                if dataset_settings.timeout is None
                else dataset_settings.timeout,
            ),
            doi_and_metadata_loaded=False,
        )

    def iter(self, recursive: bool = False) -> typing.Iterable[path.Path]:
        for dataset_settings in self.enabled_datasets_settings():
            if dataset_settings.mode != install_mode.Mode.DISABLED:
                directory = path_directory.Directory(
                    path_root=self.directory,
                    path_id=pathlib.PurePosixPath(dataset_settings.name),
                    own_doi=None,
                    metadata={},
                    server=remote.Server(
                        url=dataset_settings.url,
                        timeout=constants.DEFAULT_TIMEOUT
                        if dataset_settings.timeout is None
                        else dataset_settings.timeout,
                    ),
                    doi_and_metadata_loaded=False,
                )
                if recursive:
                    yield from directory.iter(recursive=True)
                else:
                    yield directory

    def enabled_datasets_settings(self):
        result = [
            dataset_settings
            for dataset_settings in self.name_to_dataset_settings.values()
            if dataset_settings.mode != install_mode.Mode.DISABLED
        ]
        if len(result) == 0:
            raise Exception(
                "the configuration is empty or all the datasets are disabled"
            )
        return result

    def display(
        self,
        download_tag=display.Tag(label="download", icon="↓"),
        process_tag=display.Tag(label="process", icon="⚛"),
    ):
        return display.Display(
            statuses=[
                display.Status.from_path_id_and_mode(
                    path_id=pathlib.PurePosixPath(dataset_settings.name),
                    # display both progress bars by default (RAW dataset mode)
                    dataset_mode=install_mode.Mode.RAW,
                )
                for dataset_settings in self.enabled_datasets_settings()
            ],
            output_interval=constants.CONSUMER_POLL_PERIOD,
            download_speed_samples=constants.SPEED_SAMPLES,
            process_speed_samples=constants.SPEED_SAMPLES,
            download_tag=download_tag,
            process_tag=process_tag,
        )

    def indexes_statuses(self, selector: json_index_tasks.Selector):
        return IndexesStatuses(
            name_to_status={
                dataset_settings.name: IndexStatus(
                    dataset_settings=dataset_settings,
                    current_index_files=0,
                    final_index_files=1,
                    server=remote.Server(
                        url=dataset_settings.url,
                        timeout=constants.DEFAULT_TIMEOUT
                        if dataset_settings.timeout is None
                        else dataset_settings.timeout,
                    ),
                    selector=selector,
                    downloaded_and_processed=True,
                )
                for dataset_settings in self.enabled_datasets_settings()
            }
        )

    def install(
        self,
        show_display: bool,
        workers: int,
        force: bool,
        log_directory: typing.Optional[pathlib.Path],
    ):
        with (
            display.Display(
                statuses=[
                    display.Status.from_path_id_and_mode(
                        path_id=pathlib.PurePosixPath(dataset_settings.name),
                        dataset_mode=dataset_settings.mode,
                    )
                    for dataset_settings in self.enabled_datasets_settings()
                ],
                output_interval=constants.CONSUMER_POLL_PERIOD,
                download_speed_samples=constants.SPEED_SAMPLES,
                process_speed_samples=constants.SPEED_SAMPLES,
                download_tag=display.Tag(label="download", icon="↓"),
                process_tag=display.Tag(label="decompress", icon="↔"),
            )
            if show_display
            else contextlib.nullcontext()
        ) as progress_display, task.ProcessManager(
            workers=workers, priority_levels=2, log_directory=log_directory
        ) as manager:
            indexes_statuses = IndexesStatuses(
                name_to_status={
                    dataset_settings.name: IndexStatus(
                        dataset_settings=dataset_settings,
                        current_index_files=0,
                        final_index_files=1,
                        server=remote.Server(
                            url=dataset_settings.url,
                            timeout=constants.DEFAULT_TIMEOUT
                            if dataset_settings.timeout is None
                            else dataset_settings.timeout,
                        ),
                        selector=InstallSelector(dataset_settings.mode),
                        downloaded_and_processed=True,
                    )
                    for dataset_settings in self.enabled_datasets_settings()
                }
            )
            for dataset_settings in self.enabled_datasets_settings():
                manager.schedule(
                    task=json_index_tasks.Index(
                        path_root=self.directory,
                        path_id=pathlib.PurePosixPath(dataset_settings.name),
                        server=indexes_statuses.name_to_status[
                            dataset_settings.name
                        ].server,
                        selector=indexes_statuses.name_to_status[
                            dataset_settings.name
                        ].selector,
                        priority=0,
                        force=force,
                        directory_doi=False,
                    ),
                    priority=0,
                )
            for message in manager.messages():
                if isinstance(message, task.Exception):
                    raise message
                if progress_display is not None:
                    progress_display.push(message=message)
                indexing_complete, status = indexes_statuses.push(message=message)
                if (
                    indexing_complete
                    and status is not None
                    and not status.downloaded_and_processed
                ):
                    manager.schedule(
                        task=json_index_tasks.InstallFilesRecursive(
                            path_root=self.directory,
                            path_id=pathlib.PurePosixPath(status.dataset_settings.name),
                            server=status.server,
                            selector=status.selector,
                            priority=1,
                            force=force,
                        ),
                        priority=1,
                    )

    def bibtex(
        self,
        show_display: bool,
        workers: int,
        force: bool,
        bibtex_timeout: float,
        log_directory: typing.Optional[pathlib.Path],
    ):
        with (
            display.Display(
                statuses=[
                    display.Status.from_path_id_and_mode(
                        path_id=pathlib.PurePosixPath(dataset_settings.name),
                        dataset_mode=install_mode.Mode.REMOTE,
                    )
                    for dataset_settings in self.enabled_datasets_settings()
                ],
                output_interval=constants.CONSUMER_POLL_PERIOD,
                download_speed_samples=constants.SPEED_SAMPLES,
                process_speed_samples=constants.SPEED_SAMPLES,
                download_tag=display.Tag(label="download", icon="↓"),
                process_tag=display.Tag(label="", icon=""),
            )
            if show_display
            else contextlib.nullcontext()
        ) as progress_display, task.ProcessManager(
            workers=workers, priority_levels=2, log_directory=log_directory
        ) as manager:
            selector = DoiSelector()
            for dataset_settings in self.enabled_datasets_settings():
                manager.schedule(
                    task=json_index_tasks.Index(
                        path_root=self.directory,
                        path_id=pathlib.PurePosixPath(dataset_settings.name),
                        server=remote.Server(
                            url=dataset_settings.url,
                            timeout=constants.DEFAULT_TIMEOUT
                            if dataset_settings.timeout is None
                            else dataset_settings.timeout,
                        ),
                        selector=selector,
                        priority=0,
                        force=force,
                        directory_doi=False,
                    ),
                    priority=0,
                )
            doi_to_path_ids_and_bibtex: dict[
                str, tuple[list[pathlib.PurePosixPath], str]
            ] = {}
            for message in manager.messages():
                if isinstance(message, task.Exception):
                    raise message
                if progress_display is not None:
                    progress_display.push(message)
                if isinstance(message, json_index_tasks.Doi):
                    if message.value in doi_to_path_ids_and_bibtex:
                        doi_to_path_ids_and_bibtex[message.value][0].append(
                            message.path_id
                        )
                    else:
                        try:
                            doi_to_path_ids_and_bibtex[message.value] = (
                                [message.path_id],
                                bibtex.from_doi(
                                    doi=message.value,
                                    pretty=True,
                                    timeout=bibtex_timeout,
                                ),
                            )
                        except (
                            requests.HTTPError,
                            requests.ConnectionError,
                        ) as exception:
                            doi_to_path_ids_and_bibtex[message.value] = (
                                [message.path_id],
                                f"% downloading application/x-bibtex data from https://dx.doi.org/{message.value} failed, {exception}\n",
                            )
        path_ids_and_bibtexs = [
            (sorted(path_ids), bibtex)
            for _, (path_ids, bibtex) in doi_to_path_ids_and_bibtex.items()
        ]
        path_ids_and_bibtexs.sort(
            key=lambda path_ids_and_bibtex: path_ids_and_bibtex[0][0]
        )
        result = ""
        for path_ids, bibtex_content in path_ids_and_bibtexs:
            if len(result) > 0:
                result += "\n"
            if len(path_ids) > 5:
                result += (
                    f"% {', '.join(str(path_id) for path_id in path_ids[:3])}"
                    + f", ... ({len(path_ids) - 4} more), {path_ids[-1]}\n"
                )
            else:
                result += f"% {', '.join(str(path_id) for path_id in path_ids)}\n"
            result += bibtex_content
        return result

    def map(
        self,
        switch: formats.Switch,
        store: typing.Optional[persist.Store] = None,
        show_display: bool = True,
        workers: int = multiprocessing.cpu_count() * 2,
        log_directory: typing.Optional[pathlib.Path] = None,
    ) -> typing.Iterable[typing.Any]:
        selector = MapSelector(
            enabled_types=switch.enabled_types(),
            store=None if store is None else persist.ReadOnlyStore(path=store.path),
        )
        with (
            self.display() if show_display else contextlib.nullcontext()
        ) as progress_display, task.ProcessManager(
            workers=workers, priority_levels=2, log_directory=log_directory
        ) as manager:
            indexes_statuses = self.indexes_statuses(selector=selector)
            for dataset_settings in self.enabled_datasets_settings():
                manager.schedule(
                    task=json_index_tasks.Index(
                        path_root=self.directory,
                        path_id=pathlib.PurePosixPath(dataset_settings.name),
                        server=indexes_statuses.name_to_status[
                            dataset_settings.name
                        ].server,
                        selector=indexes_statuses.name_to_status[
                            dataset_settings.name
                        ].selector,
                        priority=0,
                        force=False,
                        directory_doi=False,
                    ),
                    priority=0,
                )
            for message in manager.messages():
                logging.debug(f"{message=}")
                if isinstance(message, task.Exception):
                    raise message
                if store is not None and isinstance(message, persist.Progress):
                    store.add(str(message.path_id))
                if progress_display is not None:
                    progress_display.push(message=message)
                indexing_complete, status = indexes_statuses.push(message=message)
                logging.debug(f"{indexing_complete=}, {status=}")
                if (
                    indexing_complete
                    and status is not None
                    and not status.downloaded_and_processed
                ):
                    manager.schedule(
                        task=json_index_tasks.ProcessFilesRecursive(
                            path_root=self.directory,
                            path_id=pathlib.PurePosixPath(status.dataset_settings.name),
                            server=indexes_statuses.name_to_status[
                                status.dataset_settings.name
                            ].server,
                            process_file_class=MapProcessFile,
                            process_file_args=(),
                            process_file_kwargs={"switch": switch},
                            selector=indexes_statuses.name_to_status[
                                status.dataset_settings.name
                            ].selector,
                            priority=1,
                        ),
                        priority=1,
                    )
                if isinstance(message, MapMessage):
                    yield message.payload

    def mktree(
        self,
        root: typing.Union[str, os.PathLike],
        parents: bool = False,
        exist_ok: bool = False,
    ):
        root = pathlib.Path(root).resolve()
        root.mkdir(parents=parents, exist_ok=exist_ok)

        def mkdir_recursive(
            path_id: pathlib.PurePosixPath,
            read_root: pathlib.Path,
            write_root: pathlib.Path,
            exist_ok: bool,
        ):
            (write_root / path_id).mkdir(exist_ok=exist_ok)
            for child_directory_name in json_index.load(
                read_root / path_id / "-index.json"
            )["directories"]:
                mkdir_recursive(
                    path_id=path_id / child_directory_name,
                    read_root=read_root,
                    write_root=write_root,
                    exist_ok=exist_ok,
                )

        for dataset_settings in self.enabled_datasets_settings():
            mkdir_recursive(
                path_id=pathlib.PurePosixPath(dataset_settings.name),
                read_root=self.directory,
                write_root=root,
                exist_ok=exist_ok,
            )


def configuration_from_path(path: typing.Union[str, os.PathLike]):
    path = pathlib.Path(path).resolve()
    with open(path) as configuration_file:
        configuration = toml.load(configuration_file)
    schema.validate(configuration)
    names = set()
    for dataset in configuration["datasets"]:
        if dataset["name"] in names:
            raise Exception(
                f"two datasets share the same name \"{dataset['name']}\" in \"{path}\""
            )
        names.add(dataset["name"])
    directory = pathlib.Path(configuration["directory"])
    if not directory.is_absolute():
        directory = path.parent / directory
    directory.mkdir(exist_ok=True, parents=True)
    return Configuration(
        directory=directory,
        name_to_dataset_settings={
            dataset["name"]: DatasetSettings(
                name=dataset["name"],
                url=dataset["url"],
                mode=install_mode.Mode(dataset["mode"]),
                timeout=dataset["timeout"] if "timeout" in dataset else None,
            )
            for dataset in configuration["datasets"]
        },
    )
