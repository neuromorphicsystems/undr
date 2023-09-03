from __future__ import annotations

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
    """A processing task to be performed by a worker."""

    def __repr__(self) -> str:
        return f"{self.__class__}({self.__dict__})"

    def run(self, session: requests.Session, manager: "Manager"):
        raise NotImplementedError()


class Chain(Task):
    """A sequence of tasks that must run sequentially.

    Args:
        Task (typing.Sequence[Task]): The list of tasks to run sequentially in the given order.
    """

    def __init__(self, tasks: typing.Sequence[Task]):
        self.tasks = tasks

    def run(self, session: requests.Session, manager: "Manager"):
        for task in self.tasks:
            task.run(session=session, manager=manager)


class Manager:
    """Schedules and keeps track of tasks.

    This is an abtract class, use of one of its implementations such as :py:class:`ProcessManager` to create objects.
    """

    def schedule(self, task: Task, priority: int = 1) -> None:
        """Runs a task with the given priority.

        Tasks with lower priorities are scheduled first. The maximum priority level depends on the implementation. At least two levels, 0 (highest priority) and 1, must be supported by all implementations.

        Args:
            task (Task): The task that this manager must run (possibly on a different thread).
            priority (int, optional): Priority level. Defaults to 1.
        """
        raise NotImplementedError()

    def send_message(self, message: typing.Any) -> None:
        """Queues a message in the manager's "inbox".

        A manager is responsible for collecting messages from all tasks, which are potentially running on different threads or processes, and serving thse messages in a single-threaded fashion to a reader.

        This function is meant to be called by tasks, which have access to the manager in their :py:meth:`Task.run` function.

        Args:
            message (typing.Any): Any object. Currently implemeted managers require the message to be compatible with the :py:mod:`pickle` module.
        """
        raise NotImplementedError()


class NullManager(Manager):
    """Manager placeholder that ignores messages and raises errors if one attemps to use it to schedule more tasks.

    This manager can be used with one-off tasks whose progress need not be monitored and which do not generate more tasks.
    """

    def send_message(self, message: typing.Any):
        pass


class WorkerException(Exception):
    """An exception wrapper than can be sent across threads.

    This exception captures the stack trace of the thread that raised it to improve error reporting.

    Args:
        traceback_exception (traceback.TracebackException): Traceback of the orignal exception, can be obtained with :py:meth:`traceback.TracebackException.from_exception`.
    """

    def __init__(self, traceback_exception: traceback.TracebackException):
        self.traceback_exception = traceback_exception

    def __str__(self):
        return f"\n{''.join(self.traceback_exception.format()).strip()}"


class CloseRequest:
    """Special task used to request a worker thread shutdown."""

    pass


def send_bytes(client: socket.socket, type: bytes, message: bytes):
    """Packs and sends the bytes of a type and message.

    This message encoding scheme is used internally by :py:class:`ProcessManager`.

    Args:
        client (socket.socket): TCP client used to send messages between workers and the manager.
        type (bytes): Encoded type bytes. See :py:func:`send_bytes` for a description of type encoding.
        message (bytes): Pickled message bytes.
    """
    client.sendall(struct.pack("<cQ", type, len(message)) + message)


def send_message(client: socket.socket, type: bytes, message: typing.Any):
    """Packs and sends the bytes of a type and an unencoded message.

    This message encoding scheme is used internally by :py:class:`ProcessManager`.

    Args:
        client (socket.socket): TCP client used to send messages between workers and the manager.
        type (bytes): Encoded type bytes. See :py:func:`send_bytes` for a description of type encoding.
        message (typing.Any): Any object compatible with the :py:mod:`pickle` module.
    """
    send_bytes(client=client, type=type, message=pickle.dumps(message))


def send_type(client: socket.socket, type: bytes):
    """Packs and sends the bytes of a type that does not require a message.

    Types encode the following information.

    Messages sent by a worker to the manager.

    - ``b"n"``: Reports that the worker started a task, must not have an attached message.
    - ``b"t"``: Reports that the worker completed a task and is idle, must not have an attached message.
    - ``b"m"`` Generic message that must be forwarded to the "inbox", must have an attached message
    - ``>= 0x80``: Tells the manager to spawn a new task (a worker may do this multiple times per task). The new task priority is ``type - 0x80``. This scheme supports up to 128 priority levels. The current implementation uses 2 by default.

    Messages sent by the manager to a worker.

    - ``b"t"``: Tells the worker to start a new task, must have an attached message. The task may be an instance of :py:class:`CloseRequest`, which tells the worker to shutdown.
    - ``b"m"``: Acknowledges a generic message (message to worker ``b"m"`` request).
    - ``b"s"``: Acknowledges a task message (message to worker ``>= 0x80``  request).

    Args:
        client (socket.socket): TCP client used to send messages between workers and the manager.
        type (bytes): Encoded type bytes.
    """
    client.sendall(struct.pack("<cQ", type, 0))


def receive_message(
    client: socket.socket, unpickle: bool = True
) -> tuple[bytes, typing.Any]:
    """Reads TCP bytes until enough are received to generate a full a type and message.

    Args:
        client (socket.socket): TCP client used to send messages between workers and the manager.
        unpickle (bool, optional): Whether to pass the message bytes to :py:func:`pickle.loads`. Defaults to True.

    Returns:
        tuple[bytes, typing.Any]: The type's bytes and the decoded message. The type's bytes and the raw message's bytes are returned instead if unpickle is False.
    """
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
    """Reads TCP bytes until enough are received to generate a full a type and a raw message.

    Args:
        client (socket.socket): TCP client used to send messages between workers and the manager.

    Returns:
        tuple[bytes, bytes]: The type's bytes and the raw message's bytes.
    """
    return receive_message(client=client, unpickle=False)


def receive_type(client: socket.socket, expected_type: bytes):
    """Reads TCP bytes bytes until an acknowledge type is received.

    Args:
        client (socket.socket): TCP client used to send messages between workers and the manager.
        expected_type (bytes): The execpted acknowledge type.
    """
    type, message = receive_message(client=client, unpickle=False)
    assert type == expected_type and message == b""


class ProcessManager(Manager):
    """Implements a manager that controls a pool of worker processes.

    This class is similar to :py:class:`multiprocessing.pool.Pool` but it has better support for user-initiated shutdowns (sigint / CTRL-C) and worker-initiated shutdowns (exceptions). It also supports priorities levels.

    Whenever a worker is idle, the manager scans its (the manager's) task queues in order of priority until it finds a non-empty queue, and sends the first task from that queue to the worker. Hence, tasks with lower priorities are scheduled first. However, since a task may asynchronously spawn more tasks with arbitrary priority levels, there is no guarantee that all tasks with priority 0 spawned by a program overall are executed before all tasks with priority 1. In particular, tasks are never cancelled, even if a task with a lower priority level (i.e. more urgent) becomes available while a worker is already running a task with a higher priority level (i.e. less urgent).

    Args:
        workers (int, optional): Number of parallel workers (threads). Defaults to twice :py:func:`multiprocessing.cpu_count`.
        priority_levels (int, optional): Number of priority queues. Defaults to 2.
        log_directory (typing.Optional[pathlib.Path], optional): Directory to store log files. Logs are not generated if this is None. Defaults to None.
    """

    class ClosePolicy(enum.Enum):
        """Strategy used to terminate worker threads."""

        JOIN = 0
        """Consume all messages and shutdown threads.

        This should be used to wait for the end of the program normally.
        """

        CANCEL = 1
        """Shutdown threads without consuming buffered messages.

        This should be used to stop thread workers after user-initiated cancellation (CTRL-C).
        """

        KILL = 2
        """Kill threads without consuming buffered messages.

        This should be used after a thread raises an error, to stop the remaning worker threads.
        """

    class Proxy(Manager):
        """Manager interface that can be sent to workers.

        Since :py:class:`ProcessManager` implements a custom message passing system and owns message queues, it cannot be shared between processes. Worker processes require a handle to the manager to send messages and schedule new tasks. However, the handle does not have to be the actual manager, it is merely a means to pass around the two fuctions of its public API. This proxy prentends to be the manager but forwards messages to the actual manager using TCP. See :py:func:`send_bytes` for a description of message encoding.

        Args:
            server_port (int): Port of the manager's TCP server used to send messages between workers and the manager.
        """

        def __init__(self, server_port: int):
            self.server_port = server_port
            self.client: typing.Optional[socket.socket] = None

        def setup(self):
            """Called by each worker to create the TCP connection with the actual manager."""
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
            """Called by a worker to receive the next task.

            Returns:
                typing.Union[None, Task, CloseRequest]: None if there are no tasks waiting (but more tasks may become available in the future), a :py:class:`Task` instance if the manager returned a task for this worker, and :py:class:`CloseRequest` must shutdown.
            """
            assert self.client is not None
            send_type(client=self.client, type=b"n")
            type, message = receive_message(client=self.client)
            assert type == b"t"
            return message

        def acknowledge_and_next_task(self) -> typing.Union[None, Task, CloseRequest]:
            """Called by a worker to indicate that they completed the current task and are asking for a new one.

            Returns:
                typing.Union[None, Task, CloseRequest]: None if there are no tasks waiting (but more tasks may become available in the future), a :py:class:`Task` instance if the manager returned a task for this worker, and :py:class:`CloseRequest` must shutdown.
            """
            assert self.client is not None
            send_type(client=self.client, type=b"t")
            type, message = receive_message(client=self.client)
            assert type == b"t"
            return message

    def serve(self):
        """Server thread implementation."""
        self.server.serve_forever(poll_interval=0.1)

    @staticmethod
    def target(
        proxy: "ProcessManager.Proxy",
        log_directory: typing.Optional[pathlib.Path],
    ):
        """Worker thread implementation.

        Args:
            proxy (ProcessManager.Proxy): The manager proxy to request tasks, spawn new tasks, and send messages.
            log_directory (typing.Optional[pathlib.Path]): Directory to store log files. Logs are not generated if this is None.
        """
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
                    except Exception as exception:
                        logging.debug(exception)
                        proxy.send_message(
                            WorkerException(
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
        """Processes TCP requests for the actual manager (TCP server)."""

        def handle(self):
            """Processes a TCP request.

            See :py:func:`send_bytes` for a description of message encoding.
            """
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
                        raise Exception(f'unexpected request type "{type}"')
            except ConnectionResetError:
                pass

    def close(self, policy: "ProcessManager.ClosePolicy"):
        """Terminates the manager.

        Depending on  the value of policy, this function will return almost immediately or block until all the tasks complete. See :py:class:`ProcessManager.ClosePolicy` for details.

        Args:
            policy (ProcessManager.ClosePolicy): Termination policy for the manager and its workers.
        """
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
        """Enables the use of the "with" statement.

        Returns:
            ProcessManager: A process manager context that calls :py:meth:`close` on exit.
        """
        return self

    def __exit__(
        self,
        type: typing.Optional[typing.Type[BaseException]],
        value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
    ):
        """Enables the use of the "with" statement.

        This function calls :py:meth:`close` with the policy :py:attr:`ProcessManager.ClosePolicy.CANCEL` if there is no active exception (typically caused by a soft cancellation) and with the policy :py:attr:`ProcessManager.ClosePolicy.KILL` if there is an active exception.

        Args:
            type (typing.Optional[typing.Type[BaseException]]): None if the context exits without an exception, and the raised exception's class otherwise.
            value (typing.Optional[BaseException]): None if the context exits without an exception, and the raised exception otherwise.
            traceback (typing.Optional[types.TracebackType]): None if the context exits without an exception, and the raised exception's traceback otherwise.
        """
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
        """Iterates over the messages sent by all workers until all the tasks are complete.

        The thread that iterates over the messages has access to the manager and may use it to schedule new tasks.

        Returns:
            typing.Iterable[typing.Any]: Iterator over messages from all workers.
        """
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
