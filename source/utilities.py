import math


def parse_size(size: str) -> int:
    if size[-1] == "K":
        return round(float(size[:-1]) * 1024)
    if size[-1] == "M":
        return round(float(size[:-1]) * (1024 ** 2))
    if size[-1] == "G":
        return round(float(size[:-1]) * (1024 ** 3))
    if size[-1] == "T":
        return round(float(size[:-1]) * (1024 ** 4))
    return round(float(size))


def duration_to_string(delta: int) -> str:
    if delta < 180000000:
        return f'{"{:.0f}".format(math.floor(delta / 1e6))} s'
    if delta < 10800000000:
        return f'{"{:.0f}".format(math.floor(delta / 60e6))} min'
    if delta < 259200000000:
        return f'{"{:.0f}".format(math.floor(delta / 3600e6))} h'
    return f'{"{:.0f}".format(math.floor(delta / 86400e6))} days'


def size_to_string(size: int) -> str:
    if size < 1000:
        return f'{"{:.0f}".format(size)} B'
    if size < 1000000:
        return f'{"{:.2f}".format(size / 1000)} kB'
    if size < 1000000000:
        return f'{"{:.2f}".format(size / 1000000)} MB'
    if size < 1000000000000:
        return f'{"{:.2f}".format(size / 1000000000)} GB'
    return f'{"{:.2f}".format(size / 1000000000000)} TB'


def speed_to_string(speed: int) -> str:
    if speed < 1000:
        return f'{"{:.0f}".format(speed)} B/s'
    if speed < 1000000:
        return f'{"{:.2f}".format(speed / 1000)} kB/s'
    if speed < 1000000000:
        return f'{"{:.2f}".format(speed / 1000000)} MB/s'
    if speed < 1000000000000:
        return f'{"{:.2f}".format(speed / 1000000000)} GB/s'
    return f'{"{:.2f}".format(speed / 1000000000000)} TB/s'
