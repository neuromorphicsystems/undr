"""Progress storage utility."""

from __future__ import annotations

import collections
import dataclasses
import os
import pathlib
import sqlite3
import threading
import time
import types
import typing


@dataclasses.dataclass
class Progress:
    """Message that indicates that the given resource has been persisted."""

    path_id: pathlib.PurePosixPath
    """The resource's unique path ID.
    """


class ReadOnlyStore:
    """Stores the IDs of processed tasks.

    This store provides a method to check whether a task has been performed but it cannot be modified.
    Most users will probably prefer the writable :py:class:`Store`.

    Args:
        path (typing.Union[str, os.PathLike]): Path of the SQLite database file with extension ".db".
    """

    def __init__(
        self,
        path: typing.Union[str, os.PathLike],
    ):
        self.path = pathlib.Path(path).resolve()
        self.connection = sqlite3.connect(self.path)
        self.cursor = self.connection.cursor()

        rows = [row for row in self.cursor.execute("pragma table_info(complete)")]
        if len(rows) == 0:
            self.cursor.execute(
                "create table complete (id text primary key) without rowid"
            )
            self.connection.commit()
        elif len(rows) != 1 or rows[0] != (0, "id", "TEXT", 1, None, 1):
            raise Exception('the table "complete" does not have the expected format')

    def __contains__(self, id: str):
        """Whether the given ID has been processed.

        Args:
            id (str): The ID to check.

        Returns:
            bool: True if the file is in the store, which means that it has been processed.
        """
        return (
            self.cursor.execute(
                "select * from complete where id == ?", (id,)
            ).fetchone()
            is not None
        )

    def close(self):
        """Closes the store's database."""
        self.cursor.close()
        self.connection.close()

    def __enter__(self):
        """Enables the use of the "with" statement.

        Returns:
            Display: A store context that calls :py:meth:`close` on exit.
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
        self.close()

    def __getstate__(self):
        return pathlib.Path(self.path)

    def __setstate__(self, state: pathlib.Path):
        self.__init__(path=state)


class Store(ReadOnlyStore):
    """Stores the IDs of processed tasks.

    Args:
        path (typing.Union[str, os.PathLike]): Path of the SQLite database file with extension ".db".
        commit_maximum_delay (float, optional): How often changes are commited to the disk, in seconds. Defaults to 0.1.
        commit_maximum_inserts (int, optional): Maximum number of changes before commiting changes to the disk. Defaults to 100.
    """

    class Reset:
        """Message requesting a reset of the database (existing entries are dropped)."""

        pass

    class Commit:
        """Message requesting a commit (changes are immediately persited to the disk)."""

        pass

    def target(self):
        """Worker thread implementation."""
        thread_connection = sqlite3.connect(self.path)
        cursor = thread_connection.cursor()
        while self.running:
            commit = False
            for _ in range(0, self.commit_maximum_inserts):
                try:
                    message = self.queue.popleft()
                    if isinstance(message, Store.Reset):
                        rows = [
                            row for row in cursor.execute("pragma table_info(complete)")
                        ]
                        if len(rows) != 1 or rows[0] != (0, "id", "TEXT", 1, None, 1):
                            raise Exception(
                                'the table "complete" does not have the expected format'
                            )
                        cursor.executescript(
                            "drop table if exists complete; create table complete (id text primary key) without rowid;"
                        )
                        thread_connection.commit()
                        commit = False
                    elif isinstance(message, Store.Commit):
                        thread_connection.commit()
                        self.commit_barrier.wait()
                        commit = False
                    else:
                        cursor.execute(
                            "insert or ignore into complete values (?)", (message,)
                        )
                        commit = True
                except IndexError:
                    break
            if commit:
                thread_connection.commit()
            else:
                time.sleep(self.commit_maximum_delay)
        cursor.close()
        thread_connection.close()

    def __init__(
        self,
        path: typing.Union[str, os.PathLike],
        commit_maximum_delay: float = 0.1,
        commit_maximum_inserts: int = 100,
    ):
        super().__init__(path=path)
        self.commit_maximum_delay = commit_maximum_delay
        self.commit_maximum_inserts = commit_maximum_inserts
        self.queue: collections.deque[
            typing.Union[str, Store.Reset, Store.Commit]
        ] = collections.deque()
        self.running = True
        self.thread = threading.Thread(target=self.target, daemon=True)
        self.thread.start()
        self.commit_barrier = threading.Barrier(2)

    def add(self, id: str):
        """Adds a row to the database.

        The action is ignored if the entry is already in the database.

        Args:
            id (str): Entry to store in the database.
        """
        self.queue.append(id)

    def reset(self):
        """Drops all entries from the database."""
        self.queue.append(Store.Reset())

    def commit(self):
        """Immediately persists changes to the disk."""
        self.queue.append(Store.Commit())
        self.commit_barrier.wait()

    def close(self):
        """Closes the store's database."""
        self.running = False
        self.thread.join()
        super().close()

    def __getstate__(self):  # type: ignore
        return (
            pathlib.Path(self.path),
            self.commit_maximum_delay,
            self.commit_maximum_inserts,
        )

    def __setstate__(self, state: typing.Tuple[pathlib.Path, int, int]):  # type: ignore
        self.__init__(
            path=state[0],
            commit_maximum_delay=state[1],
            commit_maximum_inserts=state[2],
        )


if __name__ == "__main__":
    import time

    with Store("progress.db") as store:
        store.reset()
        test_ids = [
            f"nmnist/train/0/{name}"
            for name in os.listdir(
                "/Users/alex/drive/icns/undr_user/datasets/nmnist/train/0"
            )
        ]
        print(f"{len(test_ids)=}")
        begin = time.monotonic()
        for test_id in test_ids:
            store.add(test_id)
        store.commit()
        end = time.monotonic()
        print(f"{end - begin=} s ({(end - begin) / len(test_ids) * 1e3} ms/add)")
        begin = time.monotonic()
        for test_id in test_ids:
            assert test_id in store
        end = time.monotonic()
        print(f"{end - begin=} s ({(end - begin) / len(test_ids) * 1e3} ms/in)")
