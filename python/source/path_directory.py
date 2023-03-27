from __future__ import annotations

import dataclasses
import functools
import itertools
import typing

from . import constants, formats, json_index, path


@dataclasses.dataclass(frozen=True)
class Directory(path.Path):
    doi_and_metadata_loaded: bool = dataclasses.field(
        repr=False, compare=False, hash=False
    )

    def __getattribute__(self, __name: str):
        if not object.__getattribute__(self, "doi_and_metadata_loaded") and (
            __name == "metadata" or __name == "own_doi"
        ):
            index_data = json_index.load(self.local_path / "-index.json")
            if "doi" in index_data:
                object.__setattr__(self, "own_doi", index_data["doi"])
            if "metadata" in index_data:
                object.__setattr__(self, "metadata", index_data["metadata"])
            object.__setattr__(self, "doi_and_metadata_loaded", True)
        return super().__getattribute__(__name)

    @functools.lru_cache(maxsize=constants.LRU_CACHE_MAXSIZE)
    def __truediv__(self, other: str) -> path.Path:  # type: ignore
        index_data = json_index.load(self.local_path / "-index.json")
        for child_directory_name in index_data["directories"]:
            if other == child_directory_name:
                return Directory(
                    path_root=self.path_root,
                    path_id=self.path_id / child_directory_name,
                    own_doi=None,
                    metadata={},
                    server=self.server,
                    doi_and_metadata_loaded=False,
                )
        for file_data in index_data["files"]:
            if other == file_data["name"]:
                return formats.file_from_dict(data=file_data, parent=self)
        for file_data in index_data["other_files"]:
            if other == file_data["name"]:
                return path.File.from_dict(data=file_data, parent=self)
        raise Exception(f'"{other}" not found in "{self.local_path / "-index.json"}"')

    def iter(self, recursive: bool = False) -> typing.Iterable[path.Path]:
        index_data = json_index.load(self.local_path / "-index.json")
        if "doi" in index_data:
            self.__dict__["own_doi"] = index_data["doi"]
        if "metadata" in index_data:
            self.__dict__["metadata"] = index_data["metadata"]
        object.__setattr__(self, "doi_and_metadata_loaded", True)
        yield self
        for file in itertools.chain(
            (
                formats.file_from_dict(data=data, parent=self)
                for data in index_data["files"]
            ),
            (
                path.File.from_dict(data=data, parent=self)
                for data in index_data["other_files"]
            ),
        ):
            yield file
        for child_directory_name in index_data["directories"]:
            child_directory = Directory(
                path_root=self.path_root,
                path_id=self.path_id / child_directory_name,
                own_doi=None,
                metadata={},
                server=self.server,
                doi_and_metadata_loaded=False,
            )
            if recursive:
                yield from child_directory.iter(recursive=True)
            else:
                yield child_directory
