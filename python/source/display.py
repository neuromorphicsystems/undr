from __future__ import annotations

import collections
import copy
import dataclasses
import itertools
import logging
import os
import pathlib
import sys
import threading
import time
import types
import typing

from . import decode, install_mode, json_index_tasks, remote, utilities

ANSI_COLORS_ENABLED = os.getenv("ANSI_COLORS_DISABLED") is None


def format_bold(message: str) -> str:
    """Surrounds the message with ANSI escape characters for bold formatting.

    Args:
        message (str): A message to be displayed in a terminal.

    Returns:
        str: The message surrounded with ANSI escape characters, or the original message if the environment variable ``ANSI_COLORS_DISABLED`` is set.
    """
    if ANSI_COLORS_ENABLED:
        return f"\033[1m{message}\033[0m"
    return message


def format_dim(message: str) -> str:
    """Surrounds the message with ANSI escape characters for dim formatting.

    Args:
        message (str): A message to be displayed in a terminal.

    Returns:
        str: The message surrounded with ANSI escape characters, or the original message if the environment variable ``ANSI_COLORS_DISABLED`` is set.
    """
    if ANSI_COLORS_ENABLED:
        return f"\033[2m{message}\033[0m"
    return message


def format_info(message: str) -> str:
    """Adds a kangaroo icon in front of the message.

    Args:
        message (str): A message to be displayed in a terminal.

    Returns:
        str: The message with a prefix.
    """
    return f"🦘 {format_bold(message)}"


def format_error(message: str) -> str:
    """Adds a red cross mark in front of the message.

    Args:
        message (str): A message to be displayed in a terminal.

    Returns:
        str: The message with a prefix.
    """
    return f"❌ {message}"


def progress_bar(width: int, progress: typing.Optional[tuple[float, float]]) -> str:
    """Generates a progress bar compatible with terminals.

    Args:
        width (int): The progress bar width in characters.
        progress (typing.Optional[tuple[float, float]]): None yields an indeterminate progress bar, a tuple returns a two-levels progress bar (bottom and top). The tuple values must be in the range ``[0, 1]``. Use the same value twice to generate a simple (one-level) progress bar.

    Returns:
        str: The progress bar as a string, without line breaks.
    """

    width = max(width, 3)
    if progress is None:
        return "|{}|".format("░" * (width - 2))
    top = max(0.0, min(1.0, progress[0]))
    bottom = max(0.0, min(1.0, progress[1]))
    top_fill = round((width - 2) * top)
    bottom_fill = round((width - 2) * bottom)
    if top_fill < bottom_fill:
        return "|{}{}{}|".format(
            "█" * top_fill,
            "▄" * (bottom_fill - top_fill),
            "–" * (width - 2 - bottom_fill),
        )
    if top_fill > bottom_fill:
        return "|{}{}{}|".format(
            "█" * bottom_fill,
            "▀" * (top_fill - bottom_fill),
            "–" * (width - 2 - top_fill),
        )
    return "|{}{}|".format("█" * top_fill, "–" * (width - 2 - top_fill))


@dataclasses.dataclass
class DisplayProgress:
    """Represents download or process progress."""

    initial_bytes: int
    """Number of bytes already downloaded or processed when the action started.
    """

    current_bytes: int
    """Number of bytes currently downloaded or processed.
    """

    final_bytes: int
    """Total number of bytes to download or process.
    """


@dataclasses.dataclass
class Status:
    """Keeps track of download and process progress for a dataset."""

    path_id: pathlib.PurePosixPath
    """Path ID of the dataset's base directory.
    """

    mode: install_mode.Mode
    """Dataset installation mode.
    """

    indexing: bool
    """Whether the dataset has been indexed.
    """

    current_index_files: int
    """Number of index files downloaded so far.
    """

    final_index_files: int
    """Total number of index files.

    This number may increase as more index files are discovered while indexing.
    """

    download: DisplayProgress
    """Represents download progress.

    Ignored if the mode is :py:attr:`undr.install_mode.Mode.REMOTE`.
    """

    process: DisplayProgress
    """Represents process progress

    Ignored if the mode is :py:attr:`undr.install_mode.Mode.REMOTE` or :py:attr:`undr.install_mode.Mode.LOCAL`.
    """

    @classmethod
    def from_path_id_and_mode(
        cls, path_id: pathlib.PurePosixPath, dataset_mode: install_mode.Mode
    ):
        """Initializes a status from a path ID and a mode.

        Args:
            path_id (pathlib.PurePosixPath): The dataset's base directory.
            dataset_mode (install_mode.Mode): The installation mode.

        Returns:
            Status: Default initial status.
        """
        return cls(
            path_id=path_id,
            mode=dataset_mode,
            indexing=True,
            current_index_files=0,
            final_index_files=1,
            download=DisplayProgress(
                initial_bytes=0,
                current_bytes=0,
                final_bytes=0,
            ),
            process=DisplayProgress(
                initial_bytes=0,
                current_bytes=0,
                final_bytes=0,
            ),
        )

    def speeds(self, previous_status: "Status", interval: float) -> tuple[float, float]:
        """Calculates download and process speeds.

        Args:
            previous_status (Status): Past status used to calculate progress variation.
            interval (float): Time since the previous status in seconds.

        Returns:
            tuple[float, float]: download speed and process speed in bytes per second.
        """
        return (
            (self.download.current_bytes - self.download.initial_bytes)
            - (
                previous_status.download.current_bytes
                - previous_status.download.initial_bytes
            )
        ) / interval, (
            (self.process.current_bytes - self.process.initial_bytes)
            - (
                previous_status.process.current_bytes
                - previous_status.process.initial_bytes
            )
        ) / interval

    def label(self) -> str:
        """Returns the dataset's name."""
        return "/".join(self.path_id.parts)

    def progress_and_representation(
        self, download_tag: "Tag", process_tag: "Tag"
    ) -> tuple[typing.Optional[tuple[float, float]], str]:
        """Returns download and process progress in bytes and a string representation of these values.

        Args:
            download_tag (Tag): Icon and label for the download action.
            process_tag (Tag): Icon and label for the process action.

        Returns:
            tuple[tuple[float, float], str]: The first entry is None if the dataset is being indexed. Otherwise, the first entry is the progress in bytes. The second entry is the string representation of progress, which is always not None.
        """
        if self.indexing:
            return None, f"index {self.current_index_files} / {self.final_index_files}"
        representation = f"{download_tag.icon} "
        if self.download.current_bytes == self.download.final_bytes:
            representation += utilities.size_to_string(self.download.current_bytes)
        else:
            representation += f"{utilities.size_to_string(self.download.current_bytes)} / {utilities.size_to_string(self.download.final_bytes)}"
        download_progress = (
            1.0
            if self.download.final_bytes == 0
            else self.download.current_bytes / self.download.final_bytes
        )
        if self.mode == install_mode.Mode.RAW:
            representation += f" | {process_tag.icon} "
            if self.process.current_bytes == self.process.final_bytes:
                representation += utilities.size_to_string(self.process.current_bytes)
            else:
                representation += f"{utilities.size_to_string(self.process.current_bytes)} / {utilities.size_to_string(self.process.final_bytes)}"
            progress = (
                download_progress,
                1.0
                if self.process.final_bytes == 0
                else self.process.current_bytes / self.process.final_bytes,
            )
        else:
            progress = (download_progress, download_progress)
        return progress, representation

    def complete(self) -> bool:
        """Checks whether actions are complete for this dataset.

        Returns:
            bool: Whether all actions are complete.
        """
        return (
            not self.indexing
            and self.download.current_bytes == self.download.final_bytes
            and self.process.current_bytes == self.process.final_bytes
        )

    def is_parent_of(self, path_id: pathlib.PurePosixPath) -> bool:
        """Checks whether the dataset represented by this status is a parent of the given resource.

        This can be used to assign messages from a given resource to the right dataset.

        Args:
            path_id (pathlib.PurePosixPath): The path ID of the resource that may be a child of this dataset.

        Returns:
            bool: Whether this dataset is a parent of the resource.
        """
        if len(self.path_id.parts) > len(path_id.parts):
            return False
        for part, other_part in zip(self.path_id.parts, path_id.parts):
            if part != other_part:
                return False
        return True


@dataclasses.dataclass
class Tag:
    """Label and icon representing an action in a terminal."""

    label: str
    """The action label.
    """

    icon: str
    """The action's icon, typically a single non-ASCII UTF-8 character.
    """


class Speedometer:
    """Measures speed with multiple samples and a sliding window.

    Args:
        maximum_samples (int): Number of samples. Fewer samples are used for the first few speed estimations, until that number is reached.
    """

    def __init__(self, maximum_samples: int):
        assert maximum_samples > 0
        self.samples: collections.deque[float] = collections.deque()
        self.maximum_samples = maximum_samples

    def __repr__(self) -> str:
        return f"{self.__class__}({self.__dict__})"

    def add_sample(self, sample: float):
        """Passes a new sample to the speedometer.

        Args:
            sample (float): Speed sample in bytes per second.
        """
        if len(self.samples) >= self.maximum_samples:
            self.samples.popleft()
        self.samples.append(sample)

    def value(self) -> float:
        """Current speed value in bytes per second.

        Returns:
            float: Mean value of the samples.
        """

        return sum(self.samples) / len(self.samples)


def speeds(
    previous_statuses: list[Status],
    statuses: list[Status],
    interval: float,
) -> tuple[float, float]:
    """Calculates the total speed for multiple datasets.

    Args:
        previous_statuses (list[Status]): Past statuses used to calculate progress variation.
        statuses (list[Status]): Current statuses, must be the same length as `previous_statuses`.
        interval (float): Time since the previous statuses in seconds.

    Returns:
        tuple[float, float]: Overall download speed and process speed in bytes per second.
    """
    total_download = 0
    total_process = 0
    for status, previous_status in zip(statuses, previous_statuses):
        download, process = status.speeds(previous_status, interval)
        total_download += download
        total_process += process
    return total_download, total_process


class Display:
    """Display collects update messages and shows progress in a terminal.

    Args:
        statuses (list[Status]): Initial statuses for all datasets.
        output_interval (float): Time between refreshes in seconds.
        download_speed_samples (int): Size of the sliding window for download speed calculations.
        process_speed_samples (int): Size of the sliding window for process speed calculations.
        download_tag (Tag): Label and icon for the download action.
        process_tag (Tag): Label and icon for the process action.
    """

    def __init__(
        self,
        statuses: list[Status],
        output_interval: float,
        download_speed_samples: int,
        process_speed_samples: int,
        download_tag: Tag,
        process_tag: Tag,
    ):
        self.output_interval = output_interval
        self.download_speedometer = Speedometer(maximum_samples=download_speed_samples)
        self.process_speedometer = Speedometer(maximum_samples=process_speed_samples)
        self.download_tag = download_tag
        self.process_tag = process_tag
        self.names = tuple(str(status.path_id) for status in statuses)
        self.name_width = max(len(name) for name in self.names) + 4
        self.show_process_speed = any(
            status.mode == install_mode.Mode.RAW for status in statuses
        )
        self.running = True
        self.finalize = True
        self.previous_statuses = copy.deepcopy(statuses)
        self.begin = time.monotonic()
        self.previous_lines: list[str] = []
        self.message_queue: collections.deque[
            typing.Union[
                decode.Progress,
                remote.Progress,
                json_index_tasks.IndexLoaded,
                json_index_tasks.DirectoryScanned,
            ]
        ] = collections.deque()
        self.worker = threading.Thread(target=self.target)
        self.worker.daemon = True
        self.worker.start()
        logging.debug(f"{self.__dict__}")

    def push(self, message: typing.Any):
        """Processes update messages.

        Ignores messages that are not :py:class:`undr.decode.Progress`, :py:class:`undr.remote.Progress`, :py:class:`undr.json_index_tasks.IndexLoaded` or :py:class:`undr.json_index_tasks.DirectoryScanned`.

        Args:
            message (typing.Any): Message from a worker.
        """
        if isinstance(
            message,
            (
                decode.Progress,
                remote.Progress,
                json_index_tasks.IndexLoaded,
                json_index_tasks.DirectoryScanned,
            ),
        ):
            self.message_queue.append(message)

    def messages(self, statuses: list[Status]) -> list[Status]:
        """Consumes messages until the queue is empty.

        This function consumes messages until the queue is empty, not closed. More messages are likely to be queued after this function returns.

        Args:
            statuses (list[Status]): Current statuses, will be modified in-place. Use :py:func:`copy.deepcopy` to preserve the original list.

        Raises:
            RuntimeError: if a message in the queue is not :py:class:`undr.decode.Progress`, :py:class:`undr.remote.Progress`, :py:class:`undr.json_index_tasks.IndexLoaded` or :py:class:`undr.json_index_tasks.DirectoryScanned`.

        Returns:
            list[Status]: Updated statuses.
        """
        while True:
            try:
                message = self.message_queue.popleft()
                status: typing.Optional[Status] = None
                for candidate_status in statuses:
                    if candidate_status.is_parent_of(message.path_id):
                        status = candidate_status
                        break
                assert status is not None
                if isinstance(message, decode.Progress):
                    if message.initial_bytes < 0:
                        status.process.initial_bytes += message.initial_bytes
                        status.process.current_bytes += message.current_bytes
                    elif message.initial_bytes == 0:
                        status.process.current_bytes += message.current_bytes
                elif isinstance(message, remote.Progress):
                    if message.initial_bytes < 0 and not status.indexing:
                        status.download.initial_bytes += message.initial_bytes
                        status.download.current_bytes += message.current_bytes
                    if message.initial_bytes == 0:
                        status.download.current_bytes += message.current_bytes
                elif isinstance(message, json_index_tasks.IndexLoaded):
                    status.final_index_files += message.children
                elif isinstance(message, json_index_tasks.DirectoryScanned):
                    status.current_index_files += 1
                    status.download.initial_bytes += (
                        message.index_bytes.initial + message.download_bytes.initial
                    )
                    status.download.current_bytes += (
                        message.index_bytes.initial + message.download_bytes.initial
                    )
                    status.download.final_bytes += (
                        message.index_bytes.final + message.download_bytes.final
                    )
                    status.process.initial_bytes += message.process_bytes.initial
                    status.process.current_bytes += message.process_bytes.initial
                    status.process.final_bytes += message.process_bytes.final
                    if status.current_index_files == status.final_index_files:
                        status.indexing = False
                else:
                    raise RuntimeError(
                        f"unexpected message {message.__class__} ({message})"
                    )
            except IndexError:
                break
        return statuses

    def target(self):
        """Worker thread implementation."""
        next_dispatch = time.monotonic()
        self.output(
            statuses=self.previous_statuses,
            average=False,
            download_speed=0.0,
            process_speed=0.0,
        )
        previous_speed_estimation = self.begin
        while self.running:
            statuses = self.messages(copy.deepcopy(self.previous_statuses))
            now = time.monotonic()
            download_speed, process_speed = speeds(
                self.previous_statuses, statuses, now - previous_speed_estimation
            )
            previous_speed_estimation = now
            self.download_speedometer.add_sample(download_speed)
            self.process_speedometer.add_sample(process_speed)
            self.output(
                statuses=statuses,
                average=False,
                download_speed=self.download_speedometer.value(),
                process_speed=self.process_speedometer.value(),
            )
            self.previous_statuses = statuses
            next_dispatch += self.output_interval
            now = time.monotonic()
            if next_dispatch > now:
                time.sleep(next_dispatch - now)
        if self.finalize:
            statuses = self.messages(copy.deepcopy(self.previous_statuses))
            download_speed = 0.0
            process_speed = 0.0
            duration = time.monotonic() - self.begin
            for status in statuses:
                download_speed += (
                    status.download.current_bytes - status.download.initial_bytes
                ) / duration
                process_speed += (
                    status.process.current_bytes - status.process.initial_bytes
                ) / duration
            self.output(
                statuses=statuses,
                average=True,
                download_speed=download_speed,
                process_speed=process_speed,
            )
            self.previous_statuses = statuses

    def close(self):
        """Terminates the worker thread.

        This function is called automatically if display is used as a context manager.
        """
        self.running = False
        self.worker.join()

    def __enter__(self) -> "Display":
        """Enables the use of the "with" statement.

        Returns:
            Display: A display context that calls :py:meth:`close` on exit.
        """
        return self

    def __exit__(
        self,
        type: typing.Optional[typing.Type[BaseException]],
        value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
    ):
        """Enables the use of the "with" statement.

        Args:
            type (typing.Optional[typing.Type[BaseException]]): None if the context exits without an exception, and the raised exception's class otherwise.
            value (typing.Optional[BaseException]): None if the context exits without an exception, and the raised exception otherwise.
            traceback (typing.Optional[types.TracebackType]): None if the context exits without an exception, and the raised exception's traceback otherwise.
        """
        logging.debug(f"display exit with error type {type}")
        if type is not None:
            self.finalize = False
        self.close()

    def time_left(
        self, statuses: list[Status], download_speed: float, process_speed: float
    ) -> typing.Optional[float]:
        """Estimates the time left to complete the download and process actions.

        Args:
            statuses (list[Status]): Current datasets statuses.
            download_speed (float): Current speed in bytes per second.
            process_speed (float): Current speed in bytes per second.

        Returns:
            typing.Optional[float]: Estimated time left in second or None if at least one dataset is still being indexed or if the download and process speeds are zero.
        """
        download_left = 0
        process_left = 0
        for status in statuses:
            if status.indexing:
                return None
            download_left += status.download.final_bytes - status.download.current_bytes
            if status.mode == install_mode.Mode.RAW:
                process_left += (
                    status.process.final_bytes - status.process.current_bytes
                )
        if download_speed > 0 and process_speed > 0:
            return max(download_left / download_speed, process_left / process_speed)
        if download_speed > 0:
            return download_left / download_speed
        if process_speed > 0:
            return process_left / process_speed
        return None

    def output(
        self,
        statuses: list[Status],
        average: bool,
        download_speed: float,
        process_speed: float,
    ):
        """Called by the worker to generate the terminal text.

        Args:
            statuses (list[Status]): Current datasets statuses.
            average (bool): Whether the provided speeds are averages, typically used after all the actions are complete.
            download_speed (float): Current or average download speed in bytes per second.
            process_speed (float): Current or average process speed in bytes per second.
        """
        progresses_and_representations = tuple(
            status.progress_and_representation(self.download_tag, self.process_tag)
            for status in statuses
        )
        representation_width = max(
            len(representation) for _, representation in progresses_and_representations
        )
        progress_bar_width = (
            os.get_terminal_size().columns
            - self.name_width
            - (representation_width + 2)
        )
        labels = tuple(
            f"{'✓' if status.complete() else '⋅'} {status.path_id}"
            for status in statuses
        )
        time_left: typing.Optional[float] = None
        overview = ""
        if average:
            overview += "average: "
        else:
            time_left = self.time_left(statuses, download_speed, process_speed)
        overview += f"{self.download_tag.icon} {self.download_tag.label} {utilities.speed_to_string(round(download_speed))}"
        if self.show_process_speed:
            overview += f" | {self.process_tag.icon} {self.process_tag.label} {utilities.speed_to_string(round(process_speed))}"
        if time_left is not None:
            overview += f" | ⧗ {utilities.duration_to_string(time_left)} left"
        lines = [
            *(
                f"{label:<{self.name_width}}{progress_bar(progress_bar_width, progress)} {representation} "
                for label, (progress, representation) in zip(
                    labels, progresses_and_representations
                )
            ),
            "",
            overview,
        ]
        if len(self.previous_lines) > 0:
            sys.stdout.write(f"\r\033[{len(self.previous_lines)}A")
        for line, previous_line in itertools.zip_longest(lines, self.previous_lines):
            if line == previous_line:
                sys.stdout.write(f"\033[1B")
            else:
                if line is None:
                    sys.stdout.write(f"{' ' * len(previous_line)}\n")
                elif previous_line is None:
                    sys.stdout.write(f"{line}\n")
                else:
                    sys.stdout.write(f"{' ' * len(previous_line)}\r{line}\n")
        sys.stdout.flush()
        self.previous_lines = lines
