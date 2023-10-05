"""User-facing API to manipulate configuration files and trigger actions (download, decompress...)."""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import multiprocessing
import os
import pathlib
import typing

import requests

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from . import (bibtex, constants, display, formats, install_mode, json_index,
               json_index_tasks, path, path_directory, persist, remote, task,
               utilities)

schema = utilities.load_schema("undr_schema.json")
"""JSON schema for TOML settings files."""


class InstallSelector(json_index_tasks.Selector):
    """Selector for a standard installation, maps install modes to actions.

    Raises:
        ValueError: if mode is not :py:attr:`undr.install_mode.Mode.REMOTE`, :py:attr:`undr.install_mode.Mode.LOCAL`, or :py:attr:`undr.install_mode.Mode.RAW`.
    """

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
            raise ValueError(f'unexpected mode "{mode}"')

    def action(self, file: path.File) -> json_index_tasks.Selector.Action:
        return self.cached_action

    def scan_filesystem(self, directory: path_directory.Directory):
        return self.scan


class DoiSelector(json_index_tasks.Selector):
    """Selector for a DOI download."""

    def action(self, file: path.File) -> json_index_tasks.Selector.Action:
        return json_index_tasks.Selector.Action.DOI

    def scan_filesystem(self, directory: path_directory.Directory):
        return False


@dataclasses.dataclass
class DatasetSettings:
    """A dataset entry in a TOML settings file."""

    name: str
    """The dataset's name, used to name the local directory.
    """

    url: str
    """The dataset's base URL.
    """

    mode: install_mode.Mode
    """The installation mode.
    """

    timeout: typing.Optional[float]
    """Request timeout in seconds.
    """


@dataclasses.dataclass
class IndexStatus:
    """Keeps track of the indexing progress for a dataset."""

    dataset_settings: DatasetSettings
    """User-specified dataset settings.
    """

    current_index_files: int
    """Number of index files parsed.

    The dataset has been indexed if :py:attr:`current_index_files` and :py:attr:`final_index_files` are equal.
    """

    final_index_files: int
    """Total number of index files.
    """

    server: remote.Server
    """The remote server for this dataset.
    """

    selector: json_index_tasks.Selector
    """Selector to choose actions while indexing.
    """

    downloaded_and_processed: bool
    """Whether the dataset has been fully downloaded and processed.
    """

    def push(self, message: typing.Any) -> tuple[bool, typing.Optional["IndexStatus"]]:
        """Updates the status based on the message.

        Ignores messages that are not :py:class:`undr.json_index_tasks.IndexLoaded` or :py:class:`undr.json_index_tasks.DirectoryScanned`.

        Returns:
            tuple[bool, typing.Optional["IndexStatus"]]: Whether the dataset has been fully indexed and self, if self was updated.
        """
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
    """Maps dataset names to index statuses."""

    name_to_status: dict[str, IndexStatus]
    """Inner dict.
    """

    def push(self, message: typing.Any) -> tuple[bool, typing.Optional[IndexStatus]]:
        """Processes relevant messages.

        This function updates the indexing status and returns it
        if message is a :py:class:`undr.json_index_tasks.IndexLoaded` or :py:class:`undr.json_index_tasks.DirectoryScanned` object.
        If the message was the last indexing message for this dataset, the first argument is True.
        """
        if isinstance(
            message, (json_index_tasks.IndexLoaded, json_index_tasks.DirectoryScanned)
        ):
            return self.name_to_status[message.path_id.parts[0]].push(message=message)
        return False, None


@dataclasses.dataclass
class MapMessage:
    """A message generated by :py:class:`MapSelector`."""

    payload: typing.Any
    """Payload attached to this message.

    The payload may be any object type. The user is reponsible for checking message types.
    """


class MapSelector(json_index_tasks.Selector):
    """Applies a user-provided function to each file.

    Args:
        enabled_types (set[typing.Any]): The file types (a class in :py:mod:`undr.formats`) to process.
        store (typing.Optional[persist.ReadOnlyStore]): A store to check for readily processed files.
    """

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
    """Uses a switch to process files and wraps messages into :py:class:`MapMessage`.

    Args:
        file (path.File): The file to process.
        switch (formats.Switch): Switch that maps file types to actions.
    """

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
    """Represents a dataset configuration (TOML)."""

    directory: pathlib.Path
    """Local path of the root datasets directory (usually called *datasets*).
    """

    name_to_dataset_settings: dict[str, DatasetSettings]
    """Maps dataset names to their parameters.
    """

    def dataset(self, name: str) -> path_directory.Directory:
        """Returns the dataset with the given name.

        Args:
            name (str): The dataset name.

        Raises:
            ValueError: if the dataset exists but is disabled.

        Returns:
            path_directory.Directory: The dataset's root directory.
        """
        dataset_settings = self.name_to_dataset_settings[name]
        if dataset_settings.mode == install_mode.Mode.DISABLED:
            raise ValueError(f'"{name}" is disabled')
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
        """Iterates the files in the dataset.

        Args:
            recursive (bool, optional): Whether to recursively search child directories. Defaults to False.

        Returns:
            typing.Iterable[path.Path]: Iterator over the child paths. If `recursive` is false, the iterator yields the direct children (files and directories) of the root dataset directory. If `recursive` is true, the iterator yields all the children (files and directories) of the dataset.
        """
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

    def enabled_datasets_settings(self) -> list[DatasetSettings]:
        """The settings of enabled datasets.

        The list always contains at least one item (the function otherwise raises an error).

        Raises:
            RuntimeError: if all the datasets are disabled or there are no datasets.

        Returns:
            list[DatasetSettings]: The settings of the datasets that are enabled, in the same order as the configuration file.
        """
        result = [
            dataset_settings
            for dataset_settings in self.name_to_dataset_settings.values()
            if dataset_settings.mode != install_mode.Mode.DISABLED
        ]
        if len(result) == 0:
            raise RuntimeError(
                "the configuration is empty or all the datasets are disabled"
            )
        return result

    def display(
        self,
        download_tag: display.Tag = display.Tag(label="download", icon="↓"),
        process_tag: display.Tag = display.Tag(label="process", icon="⚛"),
    ) -> display.Display:
        """Returns a display that shows download and process progress for enabled datasets.

        Args:
            download_tag (display.Tag, optional): Label and icon for download. Defaults to display.Tag(label="download", icon="↓").
            process_tag (display.Tag, optional): Label and icon for process. Defaults to display.Tag(label="process", icon="⚛").

        Returns:
            display.Display: Controller for the display thread.
        """
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

    def indexes_statuses(self, selector: json_index_tasks.Selector) -> IndexesStatuses:
        """Builds an indexing report for enabled datasets.

        Args:
            selector (json_index_tasks.Selector): The selector used to index the dataset.

        Returns:
            IndexesStatuses: Index status for enaabled datasets, in the same order as the configuration file.
        """
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
        """Downloads index files and data files and decompresses data files.

        The action (index only, download, download and decompress) may be different for each dataset and is controlled by :py:class:`undr.install_mode.Mode`.

        Args:
            show_display (bool): Whether to show progress in the terminal.
            workers (int): Number of parallel workers (threads).
            force (bool): Whether to re-download resources even if they are already present locally.
            log_directory (typing.Optional[pathlib.Path]): Directory to store log files. Logs are not generated if this is None.

        Raises:
            task.WorkerException: if a worker raises an error.
        """
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
                if isinstance(message, task.WorkerException):
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
    ) -> str:
        """Downloads index files and BibTeX references for enabled datasets.

        Args:
            show_display (bool): Whether to show progress in the terminal.
            workers (int): Number of parallel workers (threads).
            force (bool): Whether to re-download resources even if they are already present locally.
            bibtex_timeout (float): Timeout for requests to https://dx.doi.org/.
            log_directory (typing.Optional[pathlib.Path]): Directory to store log files. Logs are not generated if this is None.

        Raises:
            task.WorkerException: if a worker raises an error.

        Returns:
            str: BibTeX references as a string.
        """
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
                if isinstance(message, task.WorkerException):
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
        """Applies a function to eacch file in a dataset.

        Args:
            switch (formats.Switch): Specifies the action to perform on each file type.
            store (typing.Optional[persist.Store], optional): Saves progress, makes it possible to resume interrupted processing. Defaults to None.
            show_display (bool, optional): Whether to show progress in the terminal. Defaults to True.
            workers (int, optional): Number of parallel workers (threads). Defaults to twice :py:func:`multiprocessing.cpu_count`.
            log_directory (typing.Optional[pathlib.Path], optional): Directory to store log files. Logs are not generated if this is None. Defaults to None.

        Raises:
            task.WorkerException: if a worker raises an error.

        Returns:
            typing.Iterable[typing.Any]: Iterator over the non-error messages generated by the workers.
        """
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
                if isinstance(message, task.WorkerException):
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
        """Creates a copy of the datasets' file hierarchy without the index or data files.

        This function can be combined with :py:func:`map` to implement a map-reduce algorithm over entire datasets.
            a. Use ``mktree`` to create a empty copy of the file hierarchy.
            b. Use :py:meth:`Configuration.map` to create a result file in the new hierarchy for each data file in the originall hierarchy (for instance, a file that contains a measure algorithm's performance as a single number).
            c. Collect the results ("reduce") by reading the result files in the new hierarchy.

        This approach has several benefits. The most expensive step b. runs in parallell and can be interrupted and resumed. Result files are stored in a different directory and can easily be deleted without altering the original data. The new file hierarchy prevents name clashes as long as result files are named after data files, and workers do not need to worry about directory existence since ``mktree`` runs first.

        Args:
            root (typing.Union[str, os.PathLike]): Directory where the new file hierarchy is created.
            parents (bool, optional): Whether to create the parents of the new directory, if they do not exist. Defaults to False.
            exist_ok (bool, optional): Whether to silence exeptions if the root directory already exists. Defaults to False.
        """
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


def configuration_from_path(path: typing.Union[str, os.PathLike]) -> Configuration:
    """Reads the configuration (TOML) with the given path.

    Args:
        path (typing.Union[str, os.PathLike]): Configuration file path.

    Raises:
        RuntimeError: if two datasets have the same name in the configuraation.

    Returns:
        Configuration: the parsed TOML configuration.
    """
    path = pathlib.Path(path).resolve()
    with open(path, "rb") as configuration_file:
        configuration = tomllib.load(configuration_file)
    schema.validate(configuration)
    names = set()
    for dataset in configuration["datasets"]:
        if dataset["name"] in names:
            raise RuntimeError(
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
