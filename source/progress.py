import collections
import copy
import dataclasses
import os
import pathlib
import sys
import threading
import time
import typing
from . import utilities

if typing.TYPE_CHECKING:
    from . import IndexedDirectory

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


def format_error(message: str):
    return f"❌ {message}"


def format_count(index, total):
    total_as_string = str(total)
    return format_dim(f"({index + 1:>{len(total_as_string)}d} / {total_as_string})")


@dataclasses.dataclass
class StatusUpdate:
    todo_file_count_delta: int = 0
    done_file_count_delta: int = 0
    todo_size_delta: int = 0
    done_size_delta: int = 0


@dataclasses.dataclass
class Status:
    todo_file_count: int = 0
    done_file_count: int = 0
    todo_size: int = 0
    done_size: int = 0

    def apply_update(self, status_update: StatusUpdate) -> None:
        self.todo_file_count = max(0, self.todo_file_count + status_update.todo_file_count_delta)
        self.done_file_count = max(0, self.done_file_count + status_update.done_file_count_delta)
        self.todo_size = max(0, self.todo_size + status_update.todo_size_delta)
        self.done_size = max(0, self.done_size + status_update.done_size_delta)


@dataclasses.dataclass(frozen=True)
class Group:
    pass


@dataclasses.dataclass(frozen=True)
class Phase(Group):
    name: str


@dataclasses.dataclass(frozen=True)
class ProcessDirectory(Group):
    index: int
    count: int
    name: str
    directory: "IndexedDirectory"


class Logger:
    class GroupManager:
        def __init__(self, logger: "Logger", group: Group):
            self.logger = logger
            self.group = group
            self.logger.group_begin(self.group)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.logger.group_end(self.group)

    class PollManager:
        def __init__(self, logger: "Logger", status: Status):
            self.logger = logger
            self.logger._poll_begin(status=copy.copy(status))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.logger._poll_end()

    def __init__(self, output_interval: float, speed_samples_count: int):
        self._output_interval = output_interval
        self._speed_samples_count = speed_samples_count
        self._running = False

        self._status: typing.Optional[Status] = None
        self._speed_samples: typing.Optional[collections.deque] = None
        self._begin: typing.Optional[float] = None
        self._begin_done_size: typing.Optional[int] = None
        self._worker: typing.Optional[threading.Thread] = None
        self.queue = collections.deque()

    def poll(self, status: Status) -> "Logger.PollManager":
        return Logger.PollManager(logger=self, status=status)

    def _poll_begin(self, status: Status) -> None:
        if self._running:
            raise Exception("already polling")
        self._running = True
        self._status = status
        self._speed_samples = collections.deque()
        self._begin = time.monotonic()
        self._begin_done_size = self._status.done_size

        def target() -> None:
            previous_dispatch = time.monotonic()
            previous_done_size = self._status.done_size
            self.output(status=self._status, speed=0)
            while self._running:
                now = time.monotonic()
                if now > previous_dispatch + self._output_interval:
                    if len(self._speed_samples) >= self._speed_samples_count:
                        self._speed_samples.popleft()
                    self._speed_samples.append(
                        (self._status.done_size - previous_done_size) / (now - previous_dispatch)
                    )
                    previous_dispatch = now
                    previous_done_size = self._status.done_size
                    self.output(status=self._status, speed=sum(self._speed_samples) / len(self._speed_samples))
                try:
                    message = self.queue.popleft()
                    if isinstance(message, Status):
                        self._status = message
                    elif isinstance(message, StatusUpdate):
                        self._status.apply_update(status_update=message)
                    else:
                        raise Exception(f"unsupported message type {message}")
                except IndexError:
                    time.sleep(self._output_interval)
                    pass
            while True:
                try:
                    message = self.queue.popleft()
                    if isinstance(message, Status):
                        self._status = message
                    elif isinstance(message, StatusUpdate):
                        self._status.apply_update(status_update=message)
                    else:
                        raise Exception(f"unsupported message type {message}")
                except IndexError:
                    break
            self.output(
                status=self._status,
                speed=(self._status.done_size - self._begin_done_size) / (time.monotonic() - self._begin),
            )

        self._worker = threading.Thread(target=target)
        self._worker.daemon = True
        self._worker.start()

    def _poll_end(self) -> None:
        if not self._running:
            raise Exception("not polling")
        self._running = False
        self._worker.join()
        self._worker = None
        self._status = None
        self._speed_samples = None
        self._begin = None
        self._begin_done_size = None

    def group(self, instance: Group) -> "Logger.GroupManager":
        return Logger.GroupManager(logger=self, group=instance)

    def group_begin(self, group: Group) -> None:
        raise NotImplementedError()

    def group_end(self) -> None:
        raise NotImplementedError()

    def output(self, status: Status, speed: float) -> None:
        raise NotImplementedError()

    def error(self, message: str) -> None:
        raise NotImplementedError()


class Quiet(Logger):
    def __init__(
        self,
        output_interval: float = 0.1,
        speed_samples_count: int = 30,
    ):
        super().__init__(output_interval=output_interval, speed_samples_count=speed_samples_count)

    def group_begin(self, group: Group) -> None:
        pass

    def group_end(self, group: Group) -> None:
        pass

    def output(self, status: Status, speed: float) -> None:
        pass

    def error(self, message: str) -> None:
        pass


class Printer(Logger):
    def __init__(
        self,
        output_interval: float = 0.1,
        speed_samples_count: int = 30,
        file_object: typing.IO = None,
    ):
        self.file_object = sys.stdout if file_object is None else file_object
        self.previous_message_length = 0
        super().__init__(output_interval=output_interval, speed_samples_count=speed_samples_count)
        self.indent = 0
        self.prefix = ""

    def group_begin(self, group: Group) -> None:
        if self.prefix != "":
            self.file_object.write("\n")
            self.prefix = ""
        if type(group) == Phase:
            self.file_object.write(f"{format_info(group.name)}\n")
            self.file_object.flush()
        elif type(group) == ProcessDirectory:
            self.indent += 1
            self.prefix = "{}{} {}".format("    " * self.indent, format_count(group.index, group.count), group.name)
            self.file_object.write(self.prefix)
            self.file_object.flush()

    def group_end(self, group: Group) -> None:
        if self.prefix != "":
            self.file_object.write("\n")
            self.prefix = ""
        if type(group) == Phase:
            self.file_object.write("\n")
        elif type(group) == ProcessDirectory:
            self.indent -= 1

    def output(self, status: Status, speed: float) -> None:
        total_size = status.todo_size + status.done_size
        total_count = status.todo_file_count + status.done_file_count
        if total_count == 0:
            message = self.prefix
        else:
            message = "{} - {} / {} file{}, {:.2f} % ({} / {}){}".format(
                self.prefix,
                status.done_file_count,
                total_count,
                "" if total_count == 1 else "s",
                0 if total_size == 0 else status.done_size / total_size * 100,
                utilities.size_to_string(status.done_size),
                utilities.size_to_string(total_size),
                f", {utilities.speed_to_string(speed)}" if speed > 0 else "",
            )
        self.file_object.write("\r{}\r{}".format(" " * self.previous_message_length, message))
        self.file_object.flush()
        self.previous_message_length = len(message)

    def error(self, message: str) -> None:
        if self.prefix != "":
            self.file_object.write("\n")
            self.prefix = ""
        self.file_object.write(f"{'    ' * self.indent}{format_error(message)}\n")
        self.file_object.flush()


class CheckpointStore:
    def __init__(self, path: pathlib.Path):
        self._path = path
        if self._path.is_file():
            with open(self._path, "r") as file:
                self._names = set(line.strip() for line in file if not line.isspace())
            self._file = open(self._path, "a")
        else:
            self._names = set()
            self._file = open(self._path, "w")

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def add(self, name: str) -> None:
        if not name in self._names:
            self._file.write(f"{name}\n")
            self._names.add(name)

    def has(self, name: str):
        return name in self._names

    def reset(self):
        self._file.close()
        self._file = open(self._path, "w")
        self._names.clear()
