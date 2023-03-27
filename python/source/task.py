from __future__ import annotations

import builtins
import collections
import enum
import logging
import multiprocessing
import pathlib
import pickle
import socket
import socketserver
import struct
import threading
import time
import traceback
import types
import typing

import requests

from . import constants


class Task:
    def __repr__(self):
        return f"{self.__class__}({self.__dict__})"

    def run(self, session: requests.Session, manager: "Manager") -> None:
        raise NotImplementedError()


class Chain(Task):
    def __init__(self, tasks: typing.Sequence[Task]):
        self.tasks = tasks

    def run(self, session: requests.Session, manager: "Manager"):
        for task in self.tasks:
            task.run(session=session, manager=manager)


class Manager:
    def schedule(self, task: Task, priority: int = 1) -> None:
        raise NotImplementedError()

    def send_message(self, message: typing.Any) -> None:
        raise NotImplementedError()


class NullManager(Manager):
    def send_message(self, message: typing.Any) -> None:
        pass


class Exception(builtins.Exception):
    def __init__(self, traceback_exception: traceback.TracebackException):
        self.traceback_exception = traceback_exception

    def __str__(self):
        return f"\n{''.join(self.traceback_exception.format()).strip()}"


class CloseRequest:
    pass


def send_bytes(client: socket.socket, type: bytes, message: bytes):
    client.sendall(struct.pack("<cQ", type, len(message)) + message)


def send_message(client: socket.socket, type: bytes, message: typing.Any):
    send_bytes(client=client, type=type, message=pickle.dumps(message))


def send_type(client: socket.socket, type: bytes):
    client.sendall(struct.pack("<cQ", type, 0))


def receive_message(
    client: socket.socket, unpickle: bool = True
) -> tuple[bytes, typing.Any]:
    header: bytes = b""
    while True:
        length = len(header)
        header += client.recv(9 - length)
        new_length = len(header)
        if new_length == length:
            raise ConnectionResetError()
        if new_length == 9:
            break
    type, size = struct.unpack("<cQ", header)
    if size == 0:
        return type, b""
    message = bytearray(size)
    offset = 0
    while offset < size:
        read_bytes = client.recv_into(memoryview(message)[offset:])
        if read_bytes == 0:
            raise ConnectionResetError()
        offset += read_bytes
    return type, pickle.loads(message) if unpickle else message


def receive_bytes(client: socket.socket) -> tuple[bytes, bytes]:
    return receive_message(client=client, unpickle=False)


def receive_type(client: socket.socket, expected_type: bytes):
    type, message = receive_message(client=client, unpickle=False)
    assert type == expected_type and message == b""


class ProcessManager:
    class ClosePolicy(enum.Enum):
        JOIN = 0
        CANCEL = 1
        KILL = 2

    class Proxy(Manager):
        def __init__(self, server_port: int):
            self.server_port = server_port
            self.client: typing.Optional[socket.socket] = None

        def setup(self):
            self.client = socket.create_connection(
                address=("localhost", self.server_port)
            )

        def schedule(self, task: Task, priority: int = 1):
            logging.debug(f"schedule {task} with priority {priority}")
            assert self.client is not None
            send_message(
                client=self.client,
                type=(128 + priority).to_bytes(1, byteorder="little"),
                message=task,
            )
            receive_type(client=self.client, expected_type=b"s")

        def send_message(self, message: typing.Any):
            assert self.client is not None
            send_message(client=self.client, type=b"m", message=message)
            receive_type(client=self.client, expected_type=b"m")

        def next_task(
            self,
        ) -> typing.Union[None, Task, CloseRequest]:
            assert self.client is not None
            send_type(client=self.client, type=b"n")
            type, message = receive_message(client=self.client)
            assert type == b"t"
            return message

        def acknowledge_and_next_task(self) -> typing.Union[None, Task, CloseRequest]:
            assert self.client is not None
            send_type(client=self.client, type=b"t")
            type, message = receive_message(client=self.client)
            assert type == b"t"
            return message

    def serve(self):
        self.server.serve_forever(poll_interval=0.1)

    @staticmethod
    def target(
        proxy: "ProcessManager.Proxy",
        log_directory: typing.Optional[pathlib.Path],
    ):
        try:
            if log_directory is not None:
                logging.basicConfig(
                    filename=str(
                        log_directory / f"{multiprocessing.current_process().name}.log"
                    ),
                    encoding="utf-8",
                    level=logging.DEBUG,
                    format="%(asctime)s %(message)s",
                )
            logging.debug("start worker")
            proxy.setup()
            logging.debug("connected to message server")
            with requests.Session() as session:
                active_task: typing.Union[None, Task, CloseRequest] = None
                while True:
                    if active_task is None:
                        active_task = proxy.next_task()
                    if isinstance(active_task, CloseRequest):
                        break
                    if active_task is None:
                        time.sleep(constants.WORKER_POLL_PERIOD)
                        continue
                    try:
                        logging.debug(f"run {active_task}")
                        active_task.run(session=session, manager=proxy)
                    except builtins.Exception as exception:
                        logging.debug(exception)
                        proxy.send_message(
                            Exception(
                                traceback.TracebackException.from_exception(exception)
                            )
                        )
                    active_task = proxy.acknowledge_and_next_task()

        except KeyboardInterrupt:
            pass
        except ConnectionResetError:
            pass

    def __init__(
        self,
        workers: int = multiprocessing.cpu_count() * 2,
        priority_levels: int = 2,
        log_directory: typing.Optional[pathlib.Path] = None,
    ):
        assert workers > 0
        assert priority_levels > 0 and priority_levels < 128
        self.running = True
        self.message_queue: collections.deque[typing.Any] = collections.deque()
        self.task_queues: tuple[collections.deque[bytes], ...] = tuple(
            collections.deque() for _ in range(0, priority_levels)
        )
        self.tasks_left_lock = threading.Lock()
        self.tasks_left = 0
        self.server = socketserver.ThreadingTCPServer(
            server_address=("localhost", 0),
            RequestHandlerClass=ProcessManager.RequestHandler,
        )
        self.server.daemon_threads = True
        self.server.manager = self  # type: ignore
        logging.debug(
            f"communnication server listening on port {self.server.server_address[1]}"
        )
        self.serve_thread = threading.Thread(target=self.serve, daemon=True)
        self.serve_thread.start()
        self.workers = tuple(
            multiprocessing.Process(
                target=ProcessManager.target,
                daemon=True,
                args=(
                    ProcessManager.Proxy(server_port=self.server.server_address[1]),
                    log_directory,
                ),
            )
            for _ in range(0, workers)
        )
        logging.debug("start workers")
        for worker in self.workers:
            worker.start()

    class RequestHandler(socketserver.BaseRequestHandler):
        def handle(self):
            logging.debug("start request handler")
            try:
                manager: ProcessManager = self.server.manager  # type: ignore
                while True:
                    type, message = receive_bytes(client=self.request)
                    if type == b"n" or type == b"t":
                        assert message == b""
                        if type == b"t":
                            with manager.tasks_left_lock:
                                manager.tasks_left -= 1
                        if manager.running:
                            task: typing.Optional[bytes] = None
                            for task_queue in manager.task_queues:
                                try:
                                    task = task_queue.popleft()
                                    break
                                except IndexError:
                                    continue
                            if task is None:
                                send_message(
                                    client=self.request, type=b"t", message=None
                                )
                            else:
                                send_bytes(client=self.request, type=b"t", message=task)
                        else:
                            send_message(
                                client=self.request, type=b"t", message=CloseRequest()
                            )
                    elif type == b"m":
                        manager.message_queue.append(pickle.loads(message))
                        send_type(client=self.request, type=b"m")
                    elif type >= b"\x80":
                        manager.task_queues[
                            int.from_bytes(type, byteorder="little") - 128
                        ].append(message)
                        with manager.tasks_left_lock:
                            manager.tasks_left += 1
                        send_type(client=self.request, type=b"s")
                    else:
                        raise builtins.Exception(f'unexpected request type "{type}"')
            except ConnectionResetError:
                pass

    def close(self, policy: "ProcessManager.ClosePolicy"):
        logging.debug(f"close manager with policy {policy}")
        if policy == ProcessManager.ClosePolicy.JOIN:
            collections.deque(self.messages(), maxlen=0)
            self.running = False
            for worker in self.workers:
                worker.join()
            self.server.shutdown()
            self.server.server_close()
            self.serve_thread.join()
        elif policy == ProcessManager.ClosePolicy.CANCEL:
            self.running = False
            for worker in self.workers:
                worker.join()
            self.server.shutdown()
            self.server.server_close()
            self.serve_thread.join()
        elif policy == ProcessManager.ClosePolicy.KILL:
            for worker in self.workers:
                worker.kill()
            self.server.shutdown()
            self.server.server_close()
            self.serve_thread.join()

    def __enter__(self):
        return self

    def __exit__(
        self,
        type: typing.Optional[typing.Type[BaseException]],
        value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
    ):
        logging.debug(f"manager exit with error type {type}")
        if type is None:
            self.close(policy=ProcessManager.ClosePolicy.CANCEL)
        else:
            self.close(policy=ProcessManager.ClosePolicy.KILL)
        return False

    def schedule(self, task: Task, priority: int = 1):
        logging.debug(f"schedule {task} with priority {priority}")
        self.task_queues[priority].append(pickle.dumps(task))
        with self.tasks_left_lock:
            self.tasks_left += 1

    def send_message(self, message: typing.Any):
        self.message_queue.append(message)

    def messages(self) -> typing.Iterable[typing.Any]:
        while True:
            message: typing.Any = None
            try:
                message = self.message_queue.popleft()
            except IndexError:
                with self.tasks_left_lock:
                    if self.tasks_left == 0:
                        return
                time.sleep(constants.CONSUMER_POLL_PERIOD)
                continue
            yield message
