import dataclasses
import pathlib

import requests

import undr

configuration = undr.configuration_from_path("undr.toml")


@dataclasses.dataclass
class Count:
    value: int


class Selector(undr.Selector):
    def action(self, file: undr.File) -> undr.Selector.Action:
        if isinstance(file, undr.DvsFile):
            return Selector.Action.PROCESS
        else:
            return Selector.Action.IGNORE


class CountEvents(undr.ProcessFile):
    def __init__(self, file: undr.File):
        self.file = file

    def run(self, session: requests.Session, manager: undr.Manager):
        assert isinstance(self.file, undr.DvsFile)
        self.file.attach_session(session)
        self.file.attach_manager(manager)
        file_total = 0
        for packet in self.file.packets():
            file_total += len(packet)
        manager.send_message(Count(value=file_total))


if __name__ == "__main__":
    configuration = undr.configuration_from_path("undr.toml")
    total = 0
    with configuration.display() as display, undr.ProcessManager() as manager:
        indexes_statuses = configuration.indexes_statuses(Selector())
        for dataset_settings in configuration.enabled_datasets_settings():
            manager.schedule(
                task=undr.Index(
                    path_root=configuration.directory,
                    path_id=pathlib.PurePosixPath(dataset_settings.name),
                    server=indexes_statuses.name_to_status[
                        dataset_settings.name
                    ].server,
                    selector=indexes_statuses.name_to_status[
                        dataset_settings.name
                    ].selector,
                    priority=0,
                    force=False,
                    directory_doi=False,
                ),
                priority=0,
            )
        for message in manager.messages():
            if isinstance(message, undr.Exception):
                raise message
            display.push(message)
            indexing_complete, status = indexes_statuses.push(message=message)
            if indexing_complete and status is not None:
                manager.schedule(
                    task=undr.ProcessFilesRecursive(
                        path_root=configuration.directory,
                        path_id=pathlib.PurePosixPath(status.dataset_settings.name),
                        server=indexes_statuses.name_to_status[
                            status.dataset_settings.name
                        ].server,
                        process_file_class=CountEvents,
                        process_file_args=(),
                        process_file_kwargs={},
                        selector=indexes_statuses.name_to_status[
                            status.dataset_settings.name
                        ].selector,
                        priority=1,
                    ),
                    priority=1,
                )
            if isinstance(message, Count):
                total += message.value
    print(f"{total=} events")
