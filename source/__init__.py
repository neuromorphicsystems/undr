from __future__ import annotations
import collections
import dataclasses
import datetime
import itertools
import json
import jsonschema_rs
import lzip
import lzip_extension
import math
import numpy
import os
import pathlib
import pkgutil
import threading
import toml
import typing
from . import bibtex
from . import progress
from . import raw
from . import remote


dirname = pathlib.Path(__file__).resolve().parent

undr_schema = jsonschema_rs.JSONSchema(json.loads(pkgutil.get_data("undr", "undr_schema.json").decode()))
json_index_schema = jsonschema_rs.JSONSchema(json.loads(pkgutil.get_data("undr", "-index_schema.json").decode()))

RemainingBytesError = lzip.RemainingBytesError

default_timeout = 60.0


def server_factory(type: typing.Optional[str], **kwargs) -> remote.Server:
    if type is not None:
        if type == "apache":
            return remote.ApacheServer(**kwargs)
        if type == "local":
            return remote.LocalServer(**kwargs)
        if type == "nginx":
            return remote.ApacheServer(**kwargs)
        raise RuntimeError(f"unsupported server type {type}")
    return remote.Server(**kwargs)


class SerializableTomlDecoder(toml.TomlDecoder):
    def get_empty_inline_table(self):
        return self.get_empty_table()


@dataclasses.dataclass(frozen=True)
class Path:
    path: pathlib.Path
    own_doi: typing.Optional[str]
    server: remote.Server
    parent: typing.Optional["IndexedDirectory"] = dataclasses.field(repr=False)
    metadata: dict[str, typing.Any] = dataclasses.field(repr=False)


@dataclasses.dataclass(frozen=True)
class GenericFile(Path):
    remote_path: pathlib.PurePosixPath
    progress_queue: typing.Optional[collections.deque] = dataclasses.field(default=None, repr=False)

    def lzip_path(self) -> pathlib.Path:
        return pathlib.Path(str(self.path) + ".lz")

    def decompress_path(self) -> pathlib.Path:
        return pathlib.Path(str(self.path) + ".decompress")

    def as_resource(self) -> remote.Resource:
        return remote.Resource(local_path=self.path, remote_path=self.remote_path)

    def download(self, force: bool) -> None:
        self.server.download(resource=self.as_resource(), force=force, workers_count=1)

    def decompressible(self, force: bool) -> bool:
        return (not self.path.is_file() or force) and self.lzip_path().is_file()

    def decompress(self, force: bool) -> None:
        if self.decompressible(force):
            self.decompress_path().unlink(missing_ok=True)
            with open(self.decompress_path(), "wb") as decompress_file:
                decoder = lzip_extension.Decoder(1)
                with open(self.lzip_path(), "rb") as lzip_file:
                    while True:
                        encoded_bytes = lzip_file.read(65536)
                        if len(encoded_bytes) == 0:
                            break
                        if self.progress_queue is not None:
                            self.progress_queue.append(
                                progress.StatusUpdate(
                                    todo_size_delta=-len(encoded_bytes),
                                    done_size_delta=len(encoded_bytes),
                                )
                            )
                        decompress_file.write(decoder.decompress(encoded_bytes))
                decompress_file.write(decoder.finish()[0])
            self.decompress_path().rename(self.path)
            self.lzip_path().unlink()
            if self.progress_queue is not None:
                self.progress_queue.append(progress.StatusUpdate(todo_file_count_delta=-1, done_file_count_delta=1))

    def _chunks(self, word_size: int) -> typing.Iterator[bytes]:
        assert word_size > 0
        if self.path.is_file():
            chunk_size = math.ceil(65536 / word_size) * word_size
            with open(self.path, "rb") as file_object:
                while True:
                    chunk = file_object.read(chunk_size)
                    if len(chunk) == 0:
                        break
                    if len(chunk) % word_size != 0:
                        raise RemainingBytesError(word_size=word_size, buffer=chunk)
                    yield chunk
                    if self.progress_queue is not None:
                        self.progress_queue.append(
                            progress.StatusUpdate(
                                todo_size_delta=-len(chunk),
                                done_size_delta=len(chunk),
                            )
                        )
        elif self.lzip_path().is_file():
            decoder = lzip_extension.Decoder(word_size)
            with open(self.lzip_path(), "rb") as lzip_file:
                while True:
                    encoded_bytes = lzip_file.read(65536)
                    if len(encoded_bytes) == 0:
                        break
                    yield decoder.decompress(encoded_bytes)
                    if self.progress_queue is not None:
                        self.progress_queue.append(
                            progress.StatusUpdate(
                                todo_size_delta=-len(encoded_bytes),
                                done_size_delta=len(encoded_bytes),
                            )
                        )
                decoded_bytes, remaining_bytes = decoder.finish()
                if len(decoded_bytes) > 0:
                    yield decoded_bytes
                if len(remaining_bytes) > 0:
                    raise RemainingBytesError(word_size, remaining_bytes)
        else:
            with self.server.session() as local_session:
                resource, estimated_size, _ = self.server.resource_pick(
                    session=local_session,
                    resource=self.as_resource(),
                    try_alternatives=True,
                )
                actual_size, chunks = self.server.resource_size_and_chunks(session=local_session, resource=resource)
                if self.progress_queue is not None and actual_size != estimated_size:
                    self.progress_queue.append(progress.StatusUpdate(todo_size_delta=actual_size - estimated_size))
                if resource.remote_path.suffix == ".lz":
                    decoder = lzip_extension.Decoder(word_size)
                    for chunk in chunks(65536):
                        yield decoder.decompress(chunk)
                        if self.progress_queue is not None:
                            self.progress_queue.append(
                                progress.StatusUpdate(
                                    todo_size_delta=-len(chunk),
                                    done_size_delta=len(chunk),
                                )
                            )
                    decoded_bytes, remaining_bytes = decoder.finish()
                    if len(decoded_bytes) > 0:
                        yield decoded_bytes
                    if len(remaining_bytes) > 0:
                        raise RemainingBytesError(word_size, remaining_bytes)
                else:
                    for chunk in chunks(math.ceil(65536 / word_size) * word_size):
                        if len(chunk) % word_size != 0:
                            raise RemainingBytesError(word_size=word_size, buffer=chunk)
                        yield chunk
                        if self.progress_queue is not None:
                            self.progress_queue.append(
                                progress.StatusUpdate(
                                    todo_size_delta=-len(chunk),
                                    done_size_delta=len(chunk),
                                )
                            )
        self.progress_queue.append(progress.StatusUpdate(todo_file_count_delta=-1, done_file_count_delta=1))
        object.__setattr__(self, "progress_queue", None)

    def chunks(self) -> typing.Iterable[bytes]:
        yield from self._chunks(word_size=1)

    def content_monolithic(self) -> bytes:
        return b"".join(self.chunks())

    def size(self) -> int:
        if self.path.is_file():
            return self.path.stat().st_size
        if self.lzip_path().is_file():
            return self.lzip_path().stat().st_size
        with self.server.session() as local_session:
            return self.server.resource_pick(
                session=local_session,
                resource=self.as_resource(),
                try_alternatives=True,
            )[1]


@dataclasses.dataclass(frozen=True)
class File(GenericFile):
    original_name: typing.Optional[str] = None
    sensor: typing.Optional[str] = None
    scene: typing.Optional[str] = None
    width: typing.Optional[int] = None
    height: typing.Optional[int] = None
    date: typing.Optional[datetime.datetime] = None

    def __post_init__(self):
        for field in ["original_name", "sensor", "scene", "width", "height", "date"]:
            if field in self.metadata:
                object.__setattr__(self, field, self.metadata[field])
                del self.metadata[field]


@dataclasses.dataclass(frozen=True)
class ApsFile(File):
    def packets(self) -> typing.Iterable[numpy.array]:
        dtype = numpy.dtype(raw.aps_dtype(self.width, self.height))
        for chunk in self._chunks(word_size=dtype.itemsize):
            yield numpy.frombuffer(chunk, dtype=dtype)

    def frames_monolithic(self) -> numpy.array:
        return numpy.frombuffer(self.content_monolithic(), dtype=raw.aps_dtype(self.width, self.height))


@dataclasses.dataclass(frozen=True)
class DvsFile(File):
    def packets(self) -> typing.Iterable[numpy.array]:
        for chunk in self._chunks(word_size=raw.dvs.dtype.itemsize):
            yield raw.dvs.frombuffer(chunk)

    def events_monolithic(self) -> numpy.array:
        return raw.dvs.frombuffer(self.content_monolithic())


@dataclasses.dataclass(frozen=True)
class ImuFile(File):
    def packets(self) -> typing.Iterable[numpy.array]:
        for chunk in self._chunks(word_size=raw.imu.dtype.itemsize):
            yield raw.imu.frombuffer(chunk)

    def imu_monolithic(self) -> numpy.array:
        return raw.imu.frombuffer(self.content_monolithic())


def file_factory(type: str, **kwargs):
    if type == "aps":
        return ApsFile(**kwargs)
    if type == "dvs":
        return DvsFile(**kwargs)
    if type == "imu":
        return ImuFile(**kwargs)
    raise RuntimeError(f"unsupported file type {type}")


@dataclasses.dataclass(frozen=True)
class Task:
    file: File
    handle_file: typing.Callable[[typing.Any], typing.Any]


@dataclasses.dataclass(frozen=True)
class IndexedDirectory(Path):
    provision: dataclasses.InitVar[bool]
    directories: dict[str, "IndexedDirectory"] = dataclasses.field(default=None, init=False, repr=False)
    files: dict[str, File] = dataclasses.field(default=None, init=False, repr=False)
    other_files: dict[str, GenericFile] = dataclasses.field(default=None, init=False, repr=False)

    def provision(self, logger: progress.Logger) -> None:
        self.path.mkdir(exist_ok=True)
        if not (self.path / "-index.json").is_file():
            self.server.download(
                remote.Resource.from_string(
                    local_path=self.path / "-index.json",
                    remote_path="-index.json",
                ),
                force=False,
                try_alternatives=False,
            )
        with open(self.path / "-index.json") as json_index_file:
            json_index = json.load(json_index_file)
        json_index_schema.validate(json_index)
        all_names = [
            path["name"]
            for path in itertools.chain(json_index["directories"], json_index["files"], json_index["other_files"])
        ]
        if len(all_names) != len(set(all_names)):
            unique_names = set()
            for name in all_names:
                if name in unique_names:
                    raise Exception('duplicated name "{}" in "{}"'.format(name, self.path / "-index.json"))
                unique_names.add(name)
        if "doi" in json_index:
            object.__setattr__(self, "own_doi", json_index["doi"])
            del json_index["doi"]
        object.__setattr__(
            self,
            "directories",
            {
                directory["name"]: IndexedDirectory(
                    path=self.path / directory["name"],
                    own_doi=directory["doi"] if "doi" in directory else None,
                    server=self.server.clone_with_url(self.server.join_url(directory["name"], trailing_slash=True)),
                    parent=self,
                    metadata={key: value for key, value in directory.items() if key != "name" and key != "doi"},
                )
                for directory in json_index["directories"]
            },
        )
        del json_index["directories"]
        for index, (name, directory) in enumerate(self.directories.items()):
            with logger.group(progress.ProcessDirectory(index, len(self.directories), name, directory)):
                directory.provision(logger)
        object.__setattr__(
            self,
            "files",
            {
                file["name"]: file_factory(
                    type=file["type"],
                    path=self.path / file["name"],
                    own_doi=file["doi"] if "doi" in file else None,
                    server=self.server,
                    parent=self,
                    metadata={
                        key: value for key, value in file.items() if key != "name" and key != "doi" and key != "type"
                    },
                    remote_path=pathlib.PurePosixPath(file["name"]),
                )
                for file in json_index["files"]
            },
        )
        del json_index["files"]
        object.__setattr__(
            self,
            "other_files",
            {
                other["name"]: GenericFile(
                    path=self.path / other["name"],
                    own_doi=other["doi"] if "doi" in other else None,
                    server=self.server,
                    parent=self,
                    metadata={key: value for key, value in other.items() if key != "name" and key != "doi"},
                    remote_path=pathlib.PurePosixPath(other["name"]),
                )
                for other in json_index["other_files"]
            },
        )
        del json_index["other_files"]
        object.__setattr__(self, "metadata", {**self.metadata, **json_index})

    def download(self, force: bool, logger: progress.Logger, workers_count: int) -> None:
        assert workers_count > 0
        workload = self.server.workload(
            resources=itertools.chain(
                (file.as_resource() for file in self.files.values()),
                (other_file.as_resource() for other_file in self.other_files.values()),
            ),
            force=force,
            try_alternatives=True,
            workers_count=workers_count,
        )
        workload.progress_queue = logger.queue
        with logger.poll(workload.status):
            self.server.consume(workload=workload, workers_count=workers_count)
        for index, (name, directory) in enumerate(self.directories.items()):
            with logger.group(progress.ProcessDirectory(index, len(self.directories), name, directory)):
                directory.download(
                    force=force,
                    logger=logger,
                    workers_count=workers_count,
                )

    def decompress(self, force: bool, logger: progress.Logger) -> None:
        status = progress.Status()
        workload = []
        for index, file in enumerate(itertools.chain(self.files.values(), self.other_files.values())):
            if file.decompressible(force=force):
                status.apply_update(
                    progress.StatusUpdate(
                        todo_file_count_delta=1,
                        todo_size_delta=file.lzip_path().stat().st_size,
                    )
                )
                workload.append(file)
            else:
                status.apply_update(
                    progress.StatusUpdate(
                        done_file_count_delta=1,
                        done_size_delta=file.path.stat().st_size,
                    )
                )
        with logger.poll(status):
            for file in workload:
                object.__setattr__(file, "progress_queue", logger.queue)
                file.decompress(force=force)
        for index, (name, directory) in enumerate(self.directories.items()):
            with logger.group(progress.ProcessDirectory(index, len(self.directories), name, directory)):
                directory.decompress(force=force, logger=logger)

    def clear_server_cache(self, recursive: bool) -> None:
        self.server.clear_cache()
        if recursive and self.directories is not None:
            for directory in self.directories.values():
                directory.clear_server_cache(recursive=True)

    def set_timeout(self, timeout: float, recursive: bool) -> None:
        self.server.set_timeout(timeout)
        if recursive and self.directories is not None:
            for directory in self.directories.values():
                directory.set_timeout(timeout)

    def doi_to_paths(self) -> dict[str, list[Path]]:
        doi_to_paths = {}
        if self.own_doi is not None:
            if self.own_doi in doi_to_paths:
                doi_to_paths[self.own_doi].append(self)
            else:
                doi_to_paths[self.own_doi] = [self]
        for file in itertools.chain(self.files.values(), self.other_files.values()):
            if file.own_doi is not None:
                if file.own_doi in doi_to_paths:
                    doi_to_paths[file.own_doi].append(file)
                else:
                    doi_to_paths[file.own_doi] = [file]
        for directory in self.directories.values():
            for doi, paths in directory.doi_to_paths().items():
                if doi in doi_to_paths:
                    doi_to_paths[doi].extend(paths)
                else:
                    doi_to_paths[doi] = paths
        return doi_to_paths

    def recursive_map(
        self,
        logger: progress.Logger,
        workers_count: int,
        handle_aps_file: typing.Optional[typing.Callable[[ApsFile], typing.Any]] = None,
        handle_dvs_file: typing.Optional[typing.Callable[[DvsFile], typing.Any]] = None,
        handle_imu_file: typing.Optional[typing.Callable[[ImuFile], typing.Any]] = None,
        handle_other_file: typing.Optional[typing.Callable[[GenericFile], typing.Any]] = None,
        checkpoint_store: typing.Optional[progress.CheckpointStore] = None,
    ) -> typing.Iterable[tuple["IndexedDirectory", typing.Iterable[tuple[File, typing.Any]]]]:
        assert workers_count > 0
        tasks: collections.deque[Task] = collections.deque()
        status = progress.Status()
        for file in self.files.values():
            selected = False
            if isinstance(file, ApsFile):
                if handle_aps_file is not None:
                    tasks.append(Task(file=file, handle_file=handle_aps_file))
                    selected = True
            elif isinstance(file, DvsFile):
                if handle_dvs_file is not None:
                    tasks.append(Task(file=file, handle_file=handle_dvs_file))
                    selected = True
            elif isinstance(file, ImuFile):
                if handle_imu_file is not None:
                    tasks.append(Task(file=file, handle_file=handle_imu_file))
                    selected = True
            else:
                raise Exception(f"unsupported file type {file}")
            if selected:
                status.apply_update(
                    progress.StatusUpdate(
                        todo_file_count_delta=1,
                        todo_size_delta=file.size(),
                    )
                )
        if handle_other_file is not None:
            for file in self.other_files.values():
                tasks.append(Task(file=file, handle_file=handle_other_file))
                status.apply_update(
                    progress.StatusUpdate(
                        todo_file_count_delta=1,
                        todo_size_delta=file.size(),
                    )
                )

        poll_manager = logger.poll(status)
        for task in tasks:
            object.__setattr__(task.file, "progress_queue", logger.queue)
        if min(workers_count, len(tasks)) < 2:

            def worker_target():
                try:
                    while True:
                        task = tasks.popleft()
                        yield (task.file, task.handle_file(task.file))
                except IndexError:
                    pass
                poll_manager.__exit__()

            yield (self, worker_target())
        else:
            results: collections.deque[typing.Any] = collections.deque()
            result_available = threading.Condition()
            expected_results = len(tasks)

            def consume_results():
                with result_available:
                    try:
                        index = 0
                        while index < expected_results:
                            try:
                                yield results.popleft()
                                index += 1
                            except IndexError:
                                result_available.wait(0.1)
                    except IndexError:
                        pass
                poll_manager.__exit__()

            def worker_target():
                try:
                    while True:
                        task = tasks.popleft()
                        results.append((task.file, task.handle_file(task.file)))
                        with result_available:
                            result_available.notify()
                except IndexError:
                    pass

            workers = []
            for _ in range(0, min(workers_count, len(tasks))):
                worker = threading.Thread(target=worker_target)
                worker.daemon = True
                worker.start()
                workers.append(worker)
            yield (self, consume_results())
            for worker in workers:
                worker.join()
        del status
        del worker_target
        del tasks
        self.clear_server_cache(recursive=False)
        for index, (name, directory) in enumerate(self.directories.items()):
            with logger.group(progress.ProcessDirectory(index, len(self.directories), name, directory)):
                yield from directory.recursive_map(
                    logger=logger,
                    workers_count=workers_count,
                    handle_aps_file=handle_aps_file,
                    handle_dvs_file=handle_dvs_file,
                    handle_imu_file=handle_imu_file,
                    handle_other_file=handle_other_file,
                )


@dataclasses.dataclass(frozen=True)
class Dataset(IndexedDirectory):
    url: str = ""
    mode: str = "disabled"
    server_type: typing.Optional[str] = None


@dataclasses.dataclass
class Configuration:
    directory: pathlib.Path = dataclasses.field(init=False)
    datasets: dict[str, Dataset] = dataclasses.field(init=False, repr=False)
    path: typing.Union[str, os.PathLike] = "undr.toml"

    def __post_init__(self):
        self.path = pathlib.Path(self.path).resolve()
        with open(self.path) as configuration_file:
            configuration = toml.load(configuration_file, decoder=SerializableTomlDecoder())
        undr_schema.validate(configuration)
        directory = pathlib.Path(configuration["directory"])
        if directory.is_absolute():
            self.directory = directory
        else:
            self.directory = self.path.parent / directory
        self.datasets = {
            dataset["name"]: Dataset(
                path=self.directory / dataset["name"],
                own_doi=dataset["doi"] if "doi" in dataset else None,
                server=server_factory(
                    type=dataset["server_type"] if "server_type" in dataset else None,
                    url=dataset["url"],
                    timeout=dataset["timeout"] if "timeout" in dataset else default_timeout,
                ),
                parent=None,
                metadata={
                    key: value
                    for key, value in dataset.items()
                    if key != "name" and key != "doi" and key != "url" and key != "mode" and key != "server_type"
                },
                url=dataset["url"],
                mode=dataset["mode"],
                server_type=dataset["server_type"] if "server_type" in dataset else None,
            )
            for dataset in configuration["datasets"]
        }

    def install(self, force: bool, logger: progress.Logger, workers_count: int) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        provision_count = 0
        download_count = 0
        decompress_count = 0
        phases = 0
        for dataset in self.datasets.values():
            if dataset.mode != "disabled":
                provision_count += 1
                phases = max(phases, 1)
                if dataset.mode != "remote":
                    download_count += 1
                    phases = max(phases, 2)
                    if dataset.mode != "local":
                        decompress_count += 1
                        phases = max(phases, 3)
        if provision_count > 0:
            with logger.group(progress.Phase(0, phases, "provision")):
                index = 0
                for name, dataset in self.datasets.items():
                    if dataset.mode != "disabled":
                        with logger.group(progress.ProcessDirectory(index, provision_count, name, dataset)):
                            dataset.provision(logger)
                        index += 1
        if download_count > 0:
            with logger.group(progress.Phase(1, phases, "download")):
                index = 0
                for name, dataset in self.datasets.items():
                    if dataset.mode != "disabled" and dataset.mode != "remote":
                        with logger.group(progress.ProcessDirectory(index, download_count, name, dataset)):
                            dataset.download(
                                force=force,
                                logger=logger,
                                workers_count=workers_count,
                            )
                            dataset.clear_server_cache(recursive=True)
                        index += 1
        if decompress_count > 0:
            with logger.group(progress.Phase(2, phases, "decompress")):
                index = 0
                for name, dataset in self.datasets.items():
                    if dataset.mode == "decompressed":
                        with logger.group(progress.ProcessDirectory(index, decompress_count, name, dataset)):
                            dataset.decompress(force=force, logger=logger)
                        index += 1

    def doi_to_paths(self) -> dict[str, list[Path]]:
        doi_to_paths = {}
        for dataset in self.datasets.values():
            if dataset.mode != "disabled":
                for doi, paths in dataset.doi_to_paths().items():
                    if doi in doi_to_paths:
                        doi_to_paths[doi].extend(paths)
                    else:
                        doi_to_paths[doi] = paths
        return doi_to_paths

    def bibtex(self, pretty: bool, timeout: float) -> str:
        result = ""
        for doi, paths in self.doi_to_paths().items():
            if len(result) > 0:
                result += "\n"
            result += "% {}\n".format(", ".join(path.path.relative_to(self.directory).as_posix() for path in paths))
            result += bibtex.from_doi(doi=doi, pretty=pretty, timeout=timeout)
        return result
