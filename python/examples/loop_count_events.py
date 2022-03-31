import undr

configuration = undr.configuration_from_path("undr.toml")

total = 0
for path in configuration.iter(recursive=True):
    if isinstance(path, undr.DvsFile):
        print(f"{path.path_id}")
        file_total = 0
        for packet in path.packets():
            file_total += len(packet)
        total += file_total
print(f"{total=} events")
