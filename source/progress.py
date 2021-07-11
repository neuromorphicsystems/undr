import collections
import copy
import dataclasses
import threading
import time
import typing
import sys
from . import utilities


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


class Manager:
    def __init__(self, status: Status, output_interval: float, speed_samples_count: int):
        self._status = copy.copy(status)
        self._output_interval = output_interval
        self._speed_samples_count = speed_samples_count
        self._running = True
        self._speed_samples = collections.deque()
        self._begin = time.monotonic()
        self._begin_done_size = self._status.done_size
        self.queue = collections.deque()

        def target() -> None:
            previous_dispatch = time.monotonic()
            previous_done_size = self._status.done_size
            self.output(status=self._status, last_call=False, speed=0)
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
                    self.output(
                        status=self._status, last_call=False, speed=sum(self._speed_samples) / len(self._speed_samples)
                    )
                try:
                    message = self.queue.popleft()
                    if isinstance(message, Status):
                        self._status = message
                    elif isinstance(message, StatusUpdate):
                        self._status.apply_update(status_update=message)
                    else:
                        raise Exception(f"unsupported message type {message}")
                except IndexError:
                    time.sleep(output_interval)
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
                last_call=True,
                speed=(self._status.done_size - self._begin_done_size) / (time.monotonic() - self._begin),
            )

        self._worker = threading.Thread(target=target)
        self._worker.daemon = True
        self._worker.start()

    def output(self, status: Status, last_call: bool, speed: float) -> None:
        raise NotImplementedError()

    def close(self) -> None:
        self._running = False
        self._worker.join()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Printer(Manager):
    def __init__(
        self,
        prefix: str,
        status: Status,
        output_interval: float = 0.1,
        speed_samples_count: int = 30,
        file_object: typing.IO = None,
    ):
        self.prefix = prefix
        self.file_object = sys.stdout if file_object is None else file_object
        self.previous_message_length = 0
        super().__init__(status=status, output_interval=output_interval, speed_samples_count=speed_samples_count)

    def output(self, status: Status, last_call: bool, speed: float):
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
        self.file_object.write(
            "\r{}\r{}{}".format(
                " " * self.previous_message_length,
                message,
                "\n" if last_call else "",
            )
        )
        self.file_object.flush()
        self.previous_message_length = len(message)
