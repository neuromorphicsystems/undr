import pathlib

import undr

dirname = pathlib.Path(__file__).resolve().parent

configuration = undr.configuration_from_path(dirname / "undr.toml")

total = 0
for path in configuration.iter(recursive=True):
    if isinstance(path, undr.DvsFile):
        print(f"{path.path_id}")
        file_total = 0
        for packet in path.packets():
            file_total += len(packet)
        total += file_total
print(f"{total=} events")
