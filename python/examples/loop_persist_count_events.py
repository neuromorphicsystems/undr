import json
import pathlib

import undr

configuration = undr.configuration_from_path("undr.toml")

configuration.mktree("results", exist_ok=True)
store = undr.Store("progress.db")
for path in configuration.iter(recursive=True):
    if isinstance(path, undr.DvsFile):
        if str(path.path_id) in store:
            print(f"skip {path.path_id}")
        else:
            print(f"{path.path_id}")
            file_total = 0
            for packet in path.packets():
                file_total += len(packet)
            with open(
                undr.utilities.path_with_suffix(
                    pathlib.Path("results") / path.path_id,
                    ".json",
                ),
                "w",
            ) as individual_result:
                json.dump(file_total, individual_result)
            store.add(str(path.path_id))

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
