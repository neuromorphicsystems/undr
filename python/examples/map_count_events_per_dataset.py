import pathlib

import undr

dirname = pathlib.Path(__file__).resolve().parent


def handle_dvs(file: undr.DvsFile, send_message: undr.SendMessage):
    file_total = 0
    for packet in file.packets():
        file_total += len(packet)
    send_message(
        {
            "dataset_name": file.path_id.parts[0],
            "file_total": file_total,
        }
    )


if __name__ == "__main__":
    configuration = undr.configuration_from_path(dirname / "undr.toml")
    dataset_name_to_total = {
        dataset_name: 0
        for dataset_name in configuration.name_to_dataset_settings.keys()
    }
    for message in configuration.map(switch=undr.Switch(handle_dvs=handle_dvs)):
        dataset_name_to_total[message["dataset_name"]] += message["file_total"]
    for dataset_name, total in dataset_name_to_total.items():
        print(f"{dataset_name}: {total}")
