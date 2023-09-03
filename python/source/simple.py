"""High-level functions to install datasets without using a configuration file.

The functions in this module can be very convenient for one-off downloads and simple projects.
Configuration files (undr.toml) are recommended for more complex projects.
"""

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
    """Generates a dictionary of the default datasets' names and URLs.

    The first call to this function parses the configuration file bundled with UNDR and caches the result.
    Subsequent calls return the cached value immediately.
    Hence, modifying the returned dictionary also modifies the returned value of all subsequent calls, until the Python interpreter restarts.
    Users who plan to modify the returned value may want to call ``name_to_url().copy()`` to avoid this problem.

    Returns:
        dict[str, str]: Dictionary whose keys are dataset names and whose values are matching dataset URLs.
    """
    undr_default_bytes = pkgutil.get_data("undr", "undr_default.toml")
    assert undr_default_bytes is not None
    return {
        dataset["name"]: dataset["url"]
        for dataset in toml.loads(undr_default_bytes.decode())["datasets"]
    }


def default_datasets() -> list[str]:
    """Generates a list of the default datasets' names.

    This function calls :py:func:`name_to_url` and has the same caveats regarding caching.

    Returns:
        list[str]: The names of the default datasets.
    """
    return list(name_to_url().keys())


def install(
    name: str,
    url: typing.Optional[str] = None,
    timeout: float = constants.DEFAULT_TIMEOUT,
    mode: typing.Union[str, install_mode.Mode] = install_mode.Mode.LOCAL,
    directory: typing.Union[str, pathlib.Path] = "datasets",
    show_display: bool = True,
    workers: int = multiprocessing.cpu_count() * 2,
    force: bool = False,
    log_directory: typing.Optional[pathlib.Path] = None,
):
    """Downloads (and optionally decompresses) a dataset.

    See :py:class:`undr.install_mode.Mode` for details on the different installation strategies.

    Args:
        name (str): Name of the dataset to install. Unless url is provided, it must be one of the keys returned by :py:func:`name_to_url`.
        url (typing.Optional[str], optional): URL of the dataset. Defaults to None.
        timeout (float, optional): Request timeout in seconds. Defaults to :py:attr:`undr.constants.DEFAULT_TIMEOUT`.
        mode (typing.Union[str, install_mode.Mode], optional): Installation strategy. Defaults to :py:attr:`undr.install_mode.Mode.LOCAL`.
        directory (typing.Union[str, pathlib.Path], optional): Path of the local directory to store datasets. Defaults to "datasets".
        show_display (bool, optional): Whether to show a progress bar. Defaults to True.
        workers (int, optional): Number of parallel workers (threads). Defaults to twice :py:func:`multiprocessing.cpu_count`
        force (bool, optional): Whether to re-download files even if they are already present locally. Defaults to False.
        log_directory (typing.Optional[pathlib.Path], optional): Directory to store log files. Logs are not generated if this is None. Defaults to None.
    """
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
