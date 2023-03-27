import dataclasses
import json
import pathlib

import requests

import undr

configuration = undr.configuration_from_path("undr.toml")


class Selector(undr.Selector):
    def __init__(self, store: undr.ReadOnlyStore):
        self.store = store

    def action(self, file: undr.File) -> undr.Selector.Action:
        if str(file.path_id) in self.store:
            return Selector.Action.SKIP
        elif isinstance(file, undr.DvsFile):
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
        with open(
            undr.utilities.path_with_suffix(
                pathlib.Path("results") / self.file.path_id,
                ".json",
            ),
            "w",
        ) as individual_result:
            json.dump(file_total, individual_result)
        manager.send_message(undr.persist.Progress(self.file.path_id))


if __name__ == "__main__":
    configuration = undr.configuration_from_path("undr.toml")
    configuration.mktree("results", exist_ok=True)
    store = undr.Store("progress.db")
    with configuration.display() as display, undr.ProcessManager() as manager:
        indexes_statuses = configuration.indexes_statuses(
            Selector(undr.ReadOnlyStore(store.path))
        )
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
            if isinstance(message, undr.persist.Progress):
                store.add(str(message.path_id))
            display.push(message)
            indexing_complete, status = indexes_statuses.push(message=message)
            if (
                indexing_complete
                and status is not None
                and not status.downloaded_and_processed
            ):
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

    # collect results
    total = 0
    for path in configuration.iter(recursive=True):
        if isinstance(path, undr.DvsFile):
            with open(
                undr.utilities.path_with_suffix(
                    pathlib.Path("results") / path.path_id,
                    ".json",
                ),
            ) as individual_result:
                file_total = json.load(individual_result)
                total += file_total
    print(f"{total=} events")
