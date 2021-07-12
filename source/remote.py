import collections
import copy
import dataclasses
import enum
import html.parser
import os
import pathlib
import re
import threading
import typing
from . import certificates
from . import progress
from . import utilities

certificates_bundle = certificates.bundle()
if certificates_bundle is not None:
    os.environ["REQUESTS_CA_BUNDLE"] = certificates_bundle
import requests


@dataclasses.dataclass
class Resource:
    local_path: pathlib.Path
    remote_path: pathlib.PurePosixPath

    @classmethod
    def from_string(
        cls, local_path: typing.Union[str, pathlib.Path], remote_path: typing.Union[str, pathlib.PurePosixPath]
    ) -> "Resource":
        if isinstance(local_path, str):
            local_path = pathlib.Path(local_path)
        if isinstance(remote_path, str):
            remote_path = pathlib.PurePosixPath(remote_path)
        return cls(local_path=local_path, remote_path=remote_path)

    def as_lzip(self) -> "Resource":
        return Resource(
            local_path=pathlib.Path(str(self.local_path) + ".lz"),
            remote_path=pathlib.PurePosixPath(str(self.remote_path) + ".lz"),
        )

    def download_path(self) -> pathlib.Path:
        return pathlib.Path(str(self.local_path) + ".download")

    def download_todo(self, force: bool) -> tuple[bool, int]:
        if force:
            return (True, 0)
        if self.local_path.is_file():
            return (False, self.local_path.stat().st_size)
        if self.download_path().is_file():
            return (True, self.download_path().stat().st_size)
        return (True, 0)


@dataclasses.dataclass
class Task(Resource):
    class State(enum.Enum):
        UNKNOWN = 0
        TODO = 1
        DOING = 2
        DONE = 3

    state: State = State.UNKNOWN
    to_download_size: int = 0
    downloaded_size: int = 0


class Workload:
    def __init__(self):
        self.status = progress.Status()
        self.status_lock = threading.Lock()
        self.tasks = collections.deque()
        self.done_tasks = collections.deque()
        self.progress_queue: typing.Optional[collections.deque] = None

    def update_status(self, **kwargs):
        status_update = progress.StatusUpdate(**kwargs)
        with self.status_lock:
            self.status.apply_update(status_update=status_update)
        if self.progress_queue is not None:
            self.progress_queue.append(status_update)

    def add_todo_task(self, resource: Resource, size: int) -> None:
        self.tasks.append(
            Task(
                local_path=resource.local_path,
                remote_path=resource.remote_path,
                state=Task.State.TODO,
                to_download_size=size,
                downloaded_size=0,
            )
        )
        self.update_status(
            todo_file_count_delta=1,
            todo_size_delta=size,
        )

    def add_doing_task(self, resource: Resource, to_download_size: int, downloaded_size: int) -> None:
        self.tasks.append(
            Task(
                local_path=resource.local_path,
                remote_path=resource.remote_path,
                state=Task.State.DOING,
                to_download_size=to_download_size,
                downloaded_size=downloaded_size,
            )
        )
        self.update_status(
            todo_file_count_delta=1,
            todo_size_delta=to_download_size,
            done_size_delta=downloaded_size,
        )

    def add_done_task(self, resource: Resource, size: int) -> None:
        self.done_tasks.append(
            Task(
                local_path=resource.local_path,
                remote_path=resource.remote_path,
                state=Task.State.DONE,
                to_download_size=0,
                downloaded_size=size,
            )
        )
        self.update_status(done_file_count_delta=1, done_size_delta=size)

    def resize_task(self, task: Task, actual_to_download_size: int, actual_downloaded_size: int) -> None:
        if task.to_download_size == actual_to_download_size:
            to_download_delta = 0
        else:
            to_download_delta = actual_to_download_size - task.to_download_size
            task.to_download_size = actual_to_download_size
        if task.downloaded_size == actual_downloaded_size:
            downloaded_delta = 0
        else:
            downloaded_delta = actual_downloaded_size - task.downloaded_size
            task.downloaded_size = actual_downloaded_size
        if to_download_delta != 0 or downloaded_delta != 0:
            self.update_status(todo_size_delta=to_download_delta, done_size_delta=downloaded_delta)

    def report_downloaded(self, task: Task, size: int) -> None:
        task.to_download_size = max(0, task.to_download_size - size)
        task.downloaded_size += size
        self.update_status(todo_size_delta=-size, done_size_delta=size)

    def report_done(self, task: Task) -> None:
        if task.to_download_size == 0:
            delta = 0
        else:
            delta = -task.to_download_size
        task.to_download_size += delta
        task.state = Task.State.DONE
        self.done_tasks.append(task)
        self.update_status(
            todo_size_delta=delta,
            todo_file_count_delta=-1,
            done_file_count_delta=1,
        )


class Server:
    def __init__(self, url: str, timeout: float):
        self._url: str = url
        self._timeout: float = timeout

    def __repr__(self):
        return f"{self.__class__.__name__}('{self._url}')"

    def set_timeout(self, timeout: float) -> None:
        self._timeout = timeout

    def path_to_url(self, remote_path: pathlib.PurePosixPath) -> str:
        if remote_path.parts == ():
            return self._url
        return f"{self._url}{remote_path}"

    def join_url(self, url: str, trailing_slash: bool) -> str:
        if trailing_slash and not url.endswith("/"):
            return f"{self._url}{url}/"
        return f"{self._url}{url}"

    def clone_with_url(self, url: str) -> "Server":
        clone = copy.copy(self)
        clone._url = url
        return clone

    def clear_cache(self) -> None:
        pass

    def session(self) -> requests.Session:
        return requests.Session()

    def accept_ranges_and_size(
        self, session: requests.Session, resource: Resource
    ) -> tuple[bool, typing.Optional[int]]:
        response = session.head(
            self.path_to_url(resource.remote_path),
            allow_redirects=True,
            timeout=self._timeout,
        )
        if response.status_code == 404:
            return (False, None)
        response.raise_for_status()
        return (
            "Accept-Ranges" in response.headers and response.headers["Accept-Ranges"] == "bytes",
            int(response.headers["Content-Length"]),
        )

    def resource_pick_failed(self, resources: collections.abc.Sequence[Resource]):
        raise RuntimeError(
            "error 404 (not found) returned by all the candidates ({})".format(
                ", ".join(self.path_to_url(resource.remote_path) for resource in resources)
            )
        )

    def resource_pick_from(
        self, session: requests.Session, resources: collections.abc.Sequence[Resource], force: bool
    ) -> tuple[Resource, int, int]:
        selected_resource = None
        selected_downloaded_size = None
        for resource in resources:
            must_download, downloaded_size = resource.download_todo(force)
            if must_download:
                if downloaded_size > 0:
                    selected_resource = resource
                    selected_downloaded_size = downloaded_size
                    break
            else:
                return (resource, 0, downloaded_size)
        if selected_resource is None:
            for resource in resources:
                _, total_size = self.accept_ranges_and_size(session=session, resource=resource)
                if total_size is not None:
                    return (resource, total_size, 0)
        else:
            accept_ranges, total_size = self.accept_ranges_and_size(session=session, resource=selected_resource)
            if accept_ranges:
                return (selected_resource, max(0, total_size - selected_downloaded_size), selected_downloaded_size)
            return (selected_resource, total_size, 0)
        self.resource_pick_failed(resources=resources)

    def resource_pick(
        self, session: requests.Session, resource: Resource, try_alternatives: bool
    ) -> tuple[Resource, int, int]:
        return self.resource_pick_from(
            session=session,
            resources=(resource, resource.as_lzip()) if try_alternatives else (resource,),
            force=True,
        )

    def resource_size_and_chunks(self, session: requests.Session, resource: Resource) -> typing.Iterator[bytes]:
        response = session.get(
            self.path_to_url(resource.remote_path),
            timeout=self._timeout,
            stream=True,
        )
        response.raise_for_status()
        actual_to_download_size = int(response.headers["Content-Length"])

        def chunks(chunk_size: int) -> typing.Iterator[bytes]:
            for chunk in response.iter_content(chunk_size=chunk_size):
                yield chunk

        return (actual_to_download_size, chunks)

    def workload(
        self,
        resources: collections.abc.Iterable[Resource],
        force: bool,
        try_alternatives: bool,
        workers_count: int,
    ) -> Workload:
        resources = collections.deque(resources)
        workload = Workload()

        def worker_target():
            with self.session() as local_session:
                try:
                    while True:
                        resource = resources.popleft()
                        resource, to_download_size, downloaded_size = self.resource_pick_from(
                            session=local_session,
                            resources=(resource, resource.as_lzip()) if try_alternatives else (resource,),
                            force=force,
                        )
                        if to_download_size > 0:
                            if downloaded_size > 0:
                                workload.add_doing_task(
                                    resource=resource,
                                    to_download_size=to_download_size,
                                    downloaded_size=downloaded_size,
                                )
                            else:
                                workload.add_todo_task(resource=resource, size=to_download_size)
                        elif downloaded_size > 0:
                            workload.add_done_task(resource=resource, size=downloaded_size)
                        else:
                            workload.add_todo_task(resource=resource, size=0)
                except IndexError:
                    pass

        if min(workers_count, len(resources)) < 2:
            worker_target()
        else:
            workers = []
            for _ in range(0, min(workers_count, len(resources))):
                worker = threading.Thread(target=worker_target)
                worker.daemon = True
                worker.start()
                workers.append(worker)
            for worker in workers:
                worker.join()
            del workers
        del resources
        del worker_target
        return workload

    def consume(
        self,
        workload: Workload,
        workers_count: int,
    ) -> None:
        def worker_target():
            with self.session() as local_session:
                try:
                    while True:
                        task = workload.tasks.popleft()
                        assert task.state != Task.State.UNKNOWN
                        assert task.state != Task.State.DONE
                        download_path = task.download_path()
                        if task.state == Task.State.TODO:
                            todo = True
                        elif task.state == Task.State.DOING:
                            actual_downloaded_size = download_path.stat().st_size
                            mode = "ab"
                            response = local_session.get(
                                self.path_to_url(task.remote_path),
                                timeout=self._timeout,
                                stream=True,
                                headers={"Range": f"bytes={actual_downloaded_size}-"},
                            )
                            if response.status_code == 416:
                                todo = True
                            else:
                                todo = False
                                response.raise_for_status()
                                if response.status_code != 206:
                                    raise RuntimeError(
                                        "unexpected status {} for URL {} (expected 206)".format(
                                            response.status, self.path_to_url(task.remote_path)
                                        )
                                    )
                        else:
                            raise Exception(f"unexpected task state {task.state}")
                        if todo:
                            download_path.unlink(missing_ok=True)
                            actual_downloaded_size = 0
                            mode = "wb"
                            response = local_session.get(
                                self.path_to_url(task.remote_path),
                                timeout=self._timeout,
                                stream=True,
                            )
                            response.raise_for_status()
                        actual_to_download_size = int(response.headers["Content-Length"])
                        workload.resize_task(task, actual_to_download_size, actual_downloaded_size)
                        with open(download_path, mode) as doing_file:
                            for chunk in response.iter_content(chunk_size=65536):
                                doing_file.write(chunk)
                                workload.report_downloaded(task, len(chunk))
                        download_path.rename(task.local_path)
                        workload.report_done(task)
                except IndexError:
                    pass

        if min(workers_count, len(workload.tasks)) < 2:
            worker_target()
        else:
            workers = []
            for _ in range(0, min(workers_count, len(workload.tasks))):
                worker = threading.Thread(target=worker_target)
                worker.daemon = True
                worker.start()
                workers.append(worker)
            for worker in workers:
                worker.join()
            del workers
        del worker_target
        del workload

    def download(self, resource: Resource, force: bool, try_alternatives: bool) -> None:
        workload = self.workload(resources=(resource,), force=force, try_alternatives=try_alternatives, workers_count=1)
        self.consume(workload, workers_count=1)


class LocalServer(Server):
    class LocalSession:
        def head(self, url: str, allow_redirects: bool, timeout: float):
            raise FileNotFoundError(url)

        def get(self, url: str, timeout: float, stream: bool, headers: dict[str, str]):
            raise FileNotFoundError(url)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    def session(self):
        return self.__class__.LocalSession()


class FileServer(Server):
    class Parser:
        def __init__(self):
            raise NotImplementedError("FileServer children must define a Parser subclass")

    def __init__(self, url: str, timeout: float):
        super().__init__(url, timeout)
        self._parent_to_name_to_size: dict[str, int] = {}

    def clone_with_url(self, url: str) -> "Server":
        clone = copy.copy(self)
        clone._url = url
        clone._parent_to_name_to_size = {}
        return clone

    def clear_cache(self) -> None:
        self._parent_to_name_to_size = {}

    def accept_ranges_and_size(
        self, session: requests.Session, resource: Resource
    ) -> tuple[bool, typing.Optional[int]]:
        parent_url = self.path_to_url(resource.remote_path.parent)
        if not resource.remote_path.parent in self._parent_to_name_to_size:
            response = session.get(parent_url, timeout=self._timeout)
            response.raise_for_status()
            parser = self.__class__.Parser()
            parser.feed(response.text)
            parser.close()
            self._parent_to_name_to_size[resource.remote_path.parent] = parser.name_to_size
        if resource.remote_path.name in self._parent_to_name_to_size[resource.remote_path.parent]:
            return (True, self._parent_to_name_to_size[resource.remote_path.parent][resource.remote_path.name])
        return (False, None)

    def workload(
        self,
        resources: collections.abc.Iterable[Resource],
        force: bool,
        try_alternatives: bool,
        workers_count: int,
    ) -> Workload:
        return super().workload(resources=resources, force=force, try_alternatives=try_alternatives, workers_count=1)

    def resource_pick_failed(self, resources: collections.abc.Sequence[Resource]):
        raise RuntimeError(
            "none of the candidates are listed in their parent directory ({})".format(
                ", ".join(
                    f"{resource.remote_path.name} in {self.path_to_url(resource.remote_path.parent)}"
                    for resource in resources
                )
            )
        )


class ApacheServer(FileServer):
    class Parser(html.parser.HTMLParser):
        pattern = re.compile(r"^\s*(\d+(?:\.\d+)?[KMGTP]?)\s*$")

        def __init__(self):
            super().__init__()
            self.name_to_size: dict[str, int] = {}
            self.current_href: typing.Optional[str] = None
            self.state: int = 0

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                try:
                    href = next(value for name, value in attrs if name == "href")
                    self.current_href = href
                    self.state = 1
                except StopIteration:
                    pass
            elif self.state == 1:
                if tag == "td":
                    self.state = 2
            elif self.state == 2:
                if tag == "td":
                    self.state = 3

        def handle_data(self, data):
            if self.state == 1:
                if data == "Parent Directory":
                    self.state = 0
            elif self.state == 3:
                match = self.__class__.pattern.match(data)
                if match is not None:
                    self.name_to_size[self.current_href] = utilities.parse_size(match[1])
                self.state = 0


class NginxServer(FileServer):
    class Parser(html.parser.HTMLParser):
        pattern = re.compile(r"^.*\s+(\d+(?:\.\d+)?[KMGTP]?)\s*$")

        def __init__(self):
            super().__init__()
            self.name_to_size: dict[str, int] = {}
            self.current_href: typing.Optional[str] = None
            self.state: int = 0

        def handle_starttag(self, tag, attrs):
            self.state = 0
            if tag == "a":
                try:
                    href = next(value for name, value in attrs if name == "href")
                    if href != "../":
                        self.current_href = href
                        self.state = 1
                except StopIteration:
                    pass

        def handle_data(self, data):
            if self.state == 1:
                self.state = 2
            elif self.state == 2:
                match = self.__class__.pattern.match(data)
                if match is not None:
                    self.name_to_size[self.current_href] = utilities.parse_size(match[1])
                self.state = 0
