import argparse
import json
import numpy
import pathlib
import shutil
from . import *

dirname = pathlib.Path(__file__).resolve().parent


def check_positive(value):
    value_as_int = int(value)
    if value_as_int <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return value_as_int


def configuration_and_timeout(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--configuration", "-c", default="undr.toml", help="UNDR configuration file path")
    parser.add_argument("--timeout", "-t", default=None, type=float, help="Socket timeout in seconds")


def check_aps_file(file: ApsFile) -> set[str]:
    errors = set()
    if file.width is None:
        errors.add("missing width")
    if file.height is None:
        errors.add("missing height")
    if len(errors) == 0:
        non_monotonic_ts = 0
        size_mismatches = 0
        empty = True
        try:
            previous_t = 0
            for frames in file.packets():
                empty = False
                if len(frames) > 0 and frames["t"][0] < previous_t:
                    non_monotonic_ts += 1
                    previous_t = frames["t"][-1]
                non_monotonic_ts += numpy.count_nonzero(numpy.diff(frames["t"].astype("<i8")) < 0)
                size_mismatches = numpy.count_nonzero(
                    numpy.logical_or(frames["width"] != file.width, frames["height"] != file.height)
                )
        except RemainingBytesError as error:
            empty = False
            errors.add(f"{len(error.buffer)} extra bytes")
        if empty:
            errors.add("no data found")
        if non_monotonic_ts > 0:
            errors.add("{} non-monotonic timestamp{}".format(non_monotonic_ts, "s" if non_monotonic_ts > 1 else ""))
        if size_mismatches > 0:
            errors.add("{} size mismatch{}".format(size_mismatches, "es" if size_mismatches > 1 else ""))
    return errors


def check_dvs_file(file: DvsFile) -> set[str]:
    errors = set()
    if file.width is None:
        errors.add("missing width")
    if file.height is None:
        errors.add("missing height")
    if len(errors) == 0:
        non_monotonic_ts = 0
        out_of_range_count = 0
        empty = True
        try:
            previous_t = 0
            for events in file.packets():
                empty = False
                if len(events) > 0 and events["t"][0] < previous_t:
                    non_monotonic_ts += 1
                    previous_t = events["t"][-1]
                non_monotonic_ts += numpy.count_nonzero(numpy.diff(events["t"].astype("<i8")) < 0)
                out_of_range_count += numpy.count_nonzero(
                    numpy.logical_or(events["x"] >= file.width, events["y"] >= file.height)
                )
        except RemainingBytesError as error:
            empty = False
            errors.add(f"{len(error.buffer)} extra bytes")
        if empty:
            errors.add("no data found")
        if out_of_range_count > 0:
            errors.add("{} event{} out of range".format(out_of_range_count, "s" if out_of_range_count > 1 else ""))
        if non_monotonic_ts > 0:
            errors.add("{} non-monotonic timestamp{}".format(non_monotonic_ts, "s" if non_monotonic_ts > 1 else ""))
    return errors


def check_imu_file(file: ImuFile) -> set[str]:
    errors = set()
    non_monotonic_ts = 0
    empty = True
    try:
        previous_t = 0
        for imus in file.packets():
            empty = False
            if len(imus) > 0 and imus["t"][0] < previous_t:
                non_monotonic_ts += 1
                previous_t = imus["t"][-1]
            non_monotonic_ts += numpy.count_nonzero(numpy.diff(imus["t"].astype("<i8")) < 0)
    except RemainingBytesError as error:
        errors.add(f"{len(error.buffer)} extra bytes")
    if empty:
        errors.add("no data found")
    if non_monotonic_ts > 0:
        errors.add("{} non-monotonic timestamp{}".format(non_monotonic_ts, "s" if non_monotonic_ts > 1 else ""))
    return errors


def check_other_file(file: GenericFile) -> set[str]:
    collections.deque(file.chunks(), maxlen=0)
    return set()


def check_local_directory(
    directory: IndexedDirectory,
    delete_ds_store: bool,
    format_index: bool,
) -> None:
    for path in sorted(directory.path.iterdir()):
        if path.is_file():
            if path.name == "-index.json":
                continue
            if path.suffix == ".lz":
                if not path.stem in directory.files and not path.stem in directory.other_files:
                    print(
                        format_error(
                            'the file "{}" is not listed in "{}" (compressed files must be listed without their .lz extension)'.format(
                                path, directory.path / "-index.json"
                            )
                        )
                    )
            elif not path.name in directory.files and not path.name in directory.other_files:
                if delete_ds_store and path.name == ".DS_Store":
                    path.unlink()
                    print(f"🦘 deleted {path}")
                else:
                    print(
                        format_error('the file "{}" is not listed in "{}"'.format(path, directory.path / "-index.json"))
                    )
        elif path.is_dir():
            if path.name in directory.directories:
                check_local_directory(
                    directory=directory.directories[path.name],
                    delete_ds_store=delete_ds_store,
                    format_index=format_index,
                )
            else:
                print(
                    format_error(
                        'the directory "{}" is not listed in "{}"'.format(path, directory.path / "-index.json")
                    )
                )
    if format_index:
        with open(directory.path / "-index.json") as json_index_file:
            raw_json_data = json_index_file.read()
        json_index = json.loads(raw_json_data)
        json_index_schema.validate(json_index)
        json_index["directories"].sort(key=lambda path: path["name"])
        json_index["files"].sort(key=lambda path: path["name"])
        json_index["other_files"].sort(key=lambda path: path["name"])
        new_raw_json_data = f"{json.dumps(json_index, indent=4, sort_keys=True)}\n"
        if raw_json_data != new_raw_json_data:
            with open(directory.path / "-index.json", "w") as json_index_file:
                json_index_file.write(new_raw_json_data)
            print("🦘 formatted {}".format(directory.path / "-index.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download UNDR datasets listed in a configuration file")
    subparsers = parser.add_subparsers(dest="command")
    init_parser = subparsers.add_parser("init", help="Generate a default undr.toml file")
    init_parser.add_argument("--configuration", "-c", default="undr.toml", help="UNDR configuration file path")
    install_parser = subparsers.add_parser("install", help="Provision the datasets")
    configuration_and_timeout(install_parser)
    install_parser.add_argument(
        "--force", "-f", action="store_true", help="(Re-)download files even if they already exist locally"
    )
    install_parser.add_argument(
        "--workers-count", "-w", type=check_positive, default=32, help="Number of parallel processes"
    )
    bibtex_parser = subparsers.add_parser("bibtex", help="Generate a BibTeX referencing all the datasets")
    configuration_and_timeout(bibtex_parser)
    bibtex_parser.add_argument(
        "--output", "-o", default=None, help="Specify an output file (defaults to standard output)"
    )
    doctor_parser = subparsers.add_parser("doctor", help="Check the format of a dataset")
    configuration_and_timeout(doctor_parser)
    doctor_parser.add_argument(
        "--workers-count", "-w", type=check_positive, default=32, help="Number of parallel processes"
    )
    check_local_directory_parser = subparsers.add_parser(
        "check-local-directory", help="Check the format of a local directory"
    )
    check_local_directory_parser.add_argument("path", help="Path to the local directory")
    check_local_directory_parser.add_argument(
        "--delete-ds-store", "-d", action="store_true", help="Delete macOS's .DS_Store files"
    )
    check_local_directory_parser.add_argument(
        "--format-index", "-i", action="store_true", help="Sort -index.json files and format them"
    )
    check_local_directory_parser.add_argument(
        "--workers-count", "-w", type=check_positive, default=32, help="Number of parallel processes"
    )
    args = parser.parse_args()

    if args.command == "init":
        target = pathlib.Path(args.configuration)
        if target.is_file():
            print(f"{target} already exists")
        else:
            shutil.copyfile(dirname / "undr_default.toml", target)

    if args.command == "install":
        configuration = Configuration(pathlib.Path(args.configuration), provision=False)
        if args.timeout is not None:
            for dataset in configuration.datasets.values():
                dataset.set_timeout(args.timeout, recursive=True)
        configuration.provision(force=args.force, quiet=False, workers_count=args.workers_count)

    if args.command == "bibtex":
        configuration = Configuration(pathlib.Path(args.configuration), provision=False)
        for dataset in configuration.datasets.values():
            if args.timeout is not None:
                dataset.set_timeout(args.timeout, recursive=True)
            dataset.mode = "remote"
        configuration.provision(force=False, quiet=True)
        bibtex = configuration.bibtex(pretty=True, timeout=args.timeout)
        if args.output is None:
            print(bibtex)
        else:
            with open(args.output, "wb") as bibtex_file:
                bibtex_file.write(bibtex.encode())

    if args.command == "doctor":
        configuration = Configuration(pathlib.Path(args.configuration), provision=False)
        for dataset in configuration.datasets.values():
            if args.timeout is not None:
                dataset.set_timeout(args.timeout, recursive=True)
            dataset.mode = "remote"
        configuration.provision(force=False, quiet=True, workers_count=args.workers_count)
        print(format_info("doctor"))
        for index, (name, dataset) in enumerate(configuration.datasets.items()):
            for _, results in dataset.recursive_map(
                prefix=f"{format_count(index, len(configuration.datasets))} {name}",
                handle_aps_file=check_aps_file,
                handle_dvs_file=check_dvs_file,
                handle_other_file=check_other_file,
                workers_count=args.workers_count,
            ):
                for file, errors in list(results):
                    for error in errors:
                        print(f'{format_error(error)} in "{file.path}"')

    if args.command == "check-local-directory":
        print(format_info("check local directory"))
        directory = IndexedDirectory(
            path=pathlib.Path(args.path),
            own_doi=None,
            server=server_factory(url=f"{pathlib.Path(args.path).as_posix()}/", timeout=10.0, type="local"),
            parent=None,
            metadata={},
            provision=True,
        )
        try:
            directory.download(force=False, prefix=None, workers_count=1)
        except FileNotFoundError as error:
            print(
                format_error(
                    '"{}" not found (listed in "{}")'.format(error, pathlib.Path(str(error)).parent / "-index.json")
                )
            )
        check_local_directory(directory, delete_ds_store=args.delete_ds_store, format_index=args.format_index)
        for _, results in directory.recursive_map(
            prefix=f"{directory.path}",
            handle_aps_file=check_aps_file,
            handle_dvs_file=check_dvs_file,
            handle_imu_file=check_imu_file,
            handle_other_file=check_other_file,
            workers_count=args.workers_count,
        ):
            for file, errors in list(results):
                for error in errors:
                    print(f'{format_error(error)} in "{file.path}"')
