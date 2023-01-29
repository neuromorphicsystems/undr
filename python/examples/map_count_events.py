import undr


def handle_dvs(file: undr.DvsFile, send_message: undr.SendMessage):
    file_total = 0
    for packet in file.packets():
        file_total += len(packet)
    send_message(file_total)


if __name__ == "__main__":
    configuration = undr.configuration_from_path("undr.toml")
    total = 0
    for message in configuration.map(switch=undr.Switch(handle_dvs=handle_dvs)):
        total += message
    print(f"{total=} events")
