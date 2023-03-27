import json
import pathlib

import undr


def handle_dvs(file: undr.DvsFile, send_message: undr.SendMessage):
    file_total = 0
    for packet in file.packets():
        file_total += len(packet)
    with open(
        undr.utilities.path_with_suffix(
            pathlib.Path("results") / file.path_id,
            ".json",
        ),
        "w",
    ) as individual_result:
        json.dump(file_total, individual_result)


if __name__ == "__main__":
    configuration = undr.configuration_from_path("undr.toml")
    configuration.mktree("results", exist_ok=True)
    store = undr.Store("progress.db")
    for message in configuration.map(
        switch=undr.Switch(handle_dvs=handle_dvs),
        store=store,
    ):
        continue

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
