import dataclasses
import datetime
import gc
import itertools
import json
import jsonschema_rs
import lzip
import operator
import os
import pathlib
import toml
import typing
import sys
from . import bibtex
from . import remote

dirname = pathlib.Path(__file__).resolve().parent

with open(dirname / "undr_schema.json") as undr_schema_file:
    undr_schema = jsonschema_rs.JSONSchema(json.load(undr_schema_file))

with open(dirname / "-index_schema.json") as index_schema_file:
    json_index_schema = jsonschema_rs.JSONSchema(json.load(index_schema_file))

ansi_colors_enabled = os.getenv("ANSI_COLORS_DISABLED") is None


def format_bold(message: str):
    if ansi_colors_enabled:
        return f"\033[1m{message}\033[0m"
    return message


def format_dim(message: str):
    if ansi_colors_enabled:
        return f"\033[2m{message}\033[0m"
    return message


def format_info(message: str):
    return f"🦘 {format_bold(message)}"


def format_count(index, total):
    total_as_string = str(total)
    return format_dim(f"({index + 1:>{len(total_as_string)}d} / {total_as_string})")


def server_factory(configuration_dataset) -> remote.Server:
    timeout = configuration_dataset["timeout"] if "timeout" in configuration_dataset else 10.0
    if "server_type" in configuration_dataset:
        if configuration_dataset["server_type"] == "apache":
            return remote.ApacheServer(url=configuration_dataset["url"], timeout=timeout)
        if configuration_dataset["server_type"] == "nginx":
            return remote.NginxServer(url=configuration_dataset["url"], timeout=timeout)
        raise RuntimeError("unsupported server type {}".format(configuration_dataset["server_type"]))
    return remote.Server(url=configuration_dataset["url"], timeout=timeout)


class SerializableTomlDecoder(toml.TomlDecoder):
    def get_empty_inline_table(self):
        return self.get_empty_table()


@dataclasses.dataclass
class Path:
    path: pathlib.Path
    own_doi: typing.Optional[str]
    server: remote.Server
    parent: typing.Optional["IndexedDirectory"] = dataclasses.field(repr=False)
    metadata: dict[str, typing.Any] = dataclasses.field(repr=False)


@dataclasses.dataclass
class GenericFile(Path):
    remote_path: pathlib.PurePosixPath

    def lzip_path(self) -> pathlib.Path:
        return pathlib.Path(str(self.path) + ".lz")

    def decompress_path(self) -> pathlib.Path:
        return pathlib.Path(str(self.path) + ".decompress")

    def as_resource(self) -> remote.Resource:
        return remote.Resource(local_path=self.path, remote_path=self.remote_path)

    def download(self, force: bool) -> None:
        self.server.download(resource=self.as_resource(), force=force)

    def decompressible(self, force: bool) -> bool:
        return (not self.path.is_file() or force) and self.lzip_path().is_file()

    def decompress(self, force: bool) -> None:
        if self.decompressible(force):
            self.decompress_path().unlink(missing_ok=True)
            with open(self.decompress_path(), "wb") as decompress_file:
                for chunk in lzip.decompress_file_iter(self.lzip_path()):
                    decompress_file.write(chunk)
            self.decompress_path().rename(self.path)
            self.lzip_path().unlink()


@dataclasses.dataclass
class File(GenericFile):
    type: str
    original_name: typing.Optional[str] = None
    sensor: typing.Optional[str] = None
    scene: typing.Optional[str] = None
    width: typing.Optional[int] = None
    height: typing.Optional[int] = None
    date: typing.Optional[datetime.datetime] = None

    def __post_init__(self):
        for field in ["original_name", "sensor", "scene", "width", "height", "date"]:
            if field in self.metadata:
                setattr(self, field, self.metadata[field])
                del self.metadata[field]


@dataclasses.dataclass
class IndexedDirectory(Path):
    provision: dataclasses.InitVar[bool]
    directories: list["IndexedDirectory"] = dataclasses.field(default=None, init=False, repr=False)
    files: list[File] = dataclasses.field(default=None, init=False, repr=False)
    other_files: list[GenericFile] = dataclasses.field(default=None, init=False, repr=False)

    def __post_init__(self, provision):
        if provision:
            self.provision()

    def provision(self, prefix: typing.Optional[str]) -> None:
        if prefix is not None:
            sys.stdout.write(prefix)
            sys.stdout.flush()
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
        if "doi" in json_index:
            self.own_doi = json_index["doi"]
            del json_index["doi"]
        self.directories = {
            directory["name"]: IndexedDirectory(
                path=self.path / directory["name"],
                own_doi=directory["doi"] if "doi" in directory else None,
                server=self.server.clone_with_url(self.server.join_url(directory["name"], trailing_slash=True)),
                parent=self,
                metadata={key: value for key, value in directory.items() if key != "name" and key != "doi"},
                provision=False,
            )
            for directory in json_index["directories"]
        }
        del json_index["directories"]
        indent = "" if prefix is None else " " * ((len(prefix) - len(prefix.lstrip(" "))) + 4)
        if prefix is not None:
            sys.stdout.write("\n")
            sys.stdout.flush()
        for index, (name, directory) in enumerate(self.directories.items()):
            directory.provision(
                prefix=None if prefix is None else f"{indent}{format_count(index, len(self.directories))} {name}"
            )
        self.files = {
            file["name"]: File(
                path=self.path / file["name"],
                own_doi=file["doi"] if "doi" in file else None,
                type=file["type"],
                server=self.server,
                parent=self,
                metadata={
                    key: value for key, value in file.items() if key != "name" and key != "doi" and key != "type"
                },
                remote_path=pathlib.PurePosixPath(file["name"]),
            )
            for file in json_index["files"]
        }
        del json_index["files"]
        self.other_files = {
            other["name"]: File(
                path=self.path / other["name"],
                own_doi=other["doi"] if "doi" in other else None,
                server=self.server,
                parent=self,
                metadata={key: value for key, value in other.items() if key != "name" and key != "doi"},
                remote_path=pathlib.PurePosixPath(other["name"]),
            )
            for other in json_index["other_files"]
        }
        del json_index["other_files"]
        self.metadata = {**self.metadata, **json_index}

    def download(self, force: bool, prefix: typing.Optional[str], workers_count: int = 32) -> None:
        workload = self.server.workload(
            resources=itertools.chain(
                (file.as_resource() for file in self.files.values()),
                (other_file.as_resource() for other_file in self.other_files.values()),
            ),
            force=force,
            try_alternatives=True,
            workers_count=workers_count,
        )
        printer = (
            None
            if prefix is None
            else remote.Printer(
                prefix=prefix,
                workload=workload,
            )
        )
        self.server.consume(workload=workload)
        if printer is not None:
            printer.close()
        indent = "" if prefix is None else " " * ((len(prefix) - len(prefix.lstrip(" "))) + 4)
        for index, (name, directory) in enumerate(self.directories.items()):
            directory.download(
                force=force,
                prefix=None if prefix is None else f"{indent}{format_count(index, len(self.directories))} {name}",
                workers_count=workers_count,
            )

    def decompress(self, force: bool, prefix: typing.Optional[str]) -> None:
        files_count = len(self.files) + len(self.other_files)
        if files_count == 0:
            print(f"{prefix}")
        else:
            for index, file in enumerate(itertools.chain(self.files.values(), self.other_files.values())):
                file.decompress(force=force)
                sys.stdout.write(
                    f"\r{prefix} - {index + 1} / {files_count} files, {(index + 1) / files_count * 100:.2f} %"
                )
                sys.stdout.flush()
            sys.stdout.write("\n")
            sys.stdout.flush()
        indent = "" if prefix is None else " " * ((len(prefix) - len(prefix.lstrip(" "))) + 4)
        for index, (name, directory) in enumerate(self.directories.items()):
            directory.decompress(
                force=force,
                prefix=None if prefix is None else f"{indent}{format_count(index, len(self.directories))} {name}",
            )

    def clear_cache(self) -> None:
        self.server.clear_cache()

    def set_timeout(self, timeout: float) -> None:
        self.server.set_timeout(timeout)
        if self.directories is not None:
            for directory in self.directories:
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


@dataclasses.dataclass
class Dataset(IndexedDirectory):
    mode: str = "remote"


@dataclasses.dataclass
class Configuration:
    directory: pathlib.Path = dataclasses.field(init=False)
    datasets: dict[str, IndexedDirectory] = dataclasses.field(init=False, repr=False)
    path: typing.Union[str, os.PathLike] = "undr.toml"
    provision: dataclasses.InitVar[bool] = True

    def __post_init__(self, provision):
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
                server=server_factory(dataset),
                parent=None,
                metadata={
                    key: value
                    for key, value in dataset.items()
                    if key != "name" and key != "doi" and key != "url" and key != "mode" and key != "server_type"
                },
                provision=False,
                mode=dataset["mode"],
            )
            for dataset in configuration["datasets"]
        }
        if provision:
            self.provision()

    def provision(self, force: bool, quiet: bool) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if not quiet:
            print(format_info("provision"))
        for index, (name, dataset) in enumerate(self.datasets.items()):
            dataset.provision(prefix=None if quiet else f"{format_count(index, len(self.datasets))} {name}")
        if not quiet:
            print()
            print(format_info("download"))
        download_count = sum(1 for dataset in self.datasets.values() if dataset.mode != "remote")
        for index, (name, dataset) in enumerate(self.datasets.items()):
            if dataset.mode != "remote":
                dataset.download(force=force, prefix=None if quiet else f"{format_count(index, download_count)} {name}")
                dataset.clear_cache()
                gc.collect()
        if not quiet:
            print()
            print(format_info("decompress"))
        decompress_count = sum(1 for dataset in self.datasets.values() if dataset.mode == "decompressed")
        for name, dataset in self.datasets.items():
            if dataset.mode == "decompressed":
                dataset.decompress(
                    force=force, prefix=None if quiet else f"{format_count(index, decompress_count)} {name}"
                )
                gc.collect()

    def doi_to_paths(self) -> dict[str, list[Path]]:
        doi_to_paths = {}
        for dataset in self.datasets.values():
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
