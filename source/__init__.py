import dataclasses
import json
import jsonschema_rs
import os
import pathlib
import toml
import typing
dirname = pathlib.Path(__file__).resolve().parent

with open(dirname / 'undr_schema.json') as undr_schema_file:
    undr_schema = jsonschema_rs.JSONSchema(json.load(undr_schema_file))

with open(dirname / '_index_schema.json') as _index_schema_file:
    _index_schema = jsonschema_rs.JSONSchema(json.load(_index_schema_file))


class SerializableTomlDecoder(toml.TomlDecoder):
    def get_empty_inline_table(self):
        return self.get_empty_table()


@dataclasses.dataclass
class Dataset:
    path: pathlib.Path
    url: str
    mode: str

    def __post_init__(self):
        self.path.mkdir(exist_ok=True)


@dataclasses.dataclass
class Configuration:
    directory: pathlib.Path = dataclasses.field(init=False)
    datasets: dict[str, Dataset] = dataclasses.field(init=False)
    path: typing.Union[str, os.PathLike] = 'undr.toml'

    def __post_init__(self):
        self.path = pathlib.Path(self.path).resolve()
        with open(self.path) as configuration_file:
            configuration = toml.load(
                configuration_file, decoder=SerializableTomlDecoder())
        undr_schema.validate(configuration)
        directory = pathlib.Path(configuration['directory'])
        if directory.is_absolute():
            self.directory = directory
        else:
            self.directory = self.path.parent / directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.datasets = {
            dataset['name']: Dataset(
                self.directory / dataset['name'], dataset['url'], dataset['mode'])
            for dataset in configuration['datasets']
        }
        print(self.datasets)
