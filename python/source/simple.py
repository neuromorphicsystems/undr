from __future__ import annotations

import functools
import multiprocessing
import pathlib
import pkgutil
import typing

import toml

from . import configuration, constants, install_mode


@functools.lru_cache(maxsize=None)
def name_to_url() -> dict[str, str]:
    undr_default_bytes = pkgutil.get_data("undr", "undr_default.toml")
    assert undr_default_bytes is not None
    return {
        dataset["name"]: dataset["url"]
        for dataset in toml.loads(undr_default_bytes.decode())["datasets"]
    }


def default_datasets() -> list[str]:
    return list(name_to_url().keys())


def install(
    name: str,
    url: typing.Union[str, None] = None,
    timeout: float = constants.DEFAULT_TIMEOUT,
    mode: typing.Union[str, install_mode.Mode] = install_mode.Mode.LOCAL,
    directory: typing.Union[str, pathlib.Path] = "datasets",
    show_display: bool = True,
    workers: int = multiprocessing.cpu_count() * 2,
    force: bool = False,
    log_directory: typing.Union[pathlib.Path, None] = None,
):
    if url is None:
        url = name_to_url()[name]
    if isinstance(mode, str):
        mode = install_mode.Mode(mode)
    if isinstance(directory, str):
        directory = pathlib.Path(directory)
    directory = directory.resolve()
    directory.mkdir(exist_ok=True, parents=True)
    configuration.Configuration(
        directory=directory,
        name_to_dataset_settings={
            name: configuration.DatasetSettings(
                name=name,
                url=url,
                mode=mode,
                timeout=timeout,
            )
        },
    ).install(
        show_display=show_display,
        workers=workers,
        force=force,
        log_directory=log_directory,
    )
