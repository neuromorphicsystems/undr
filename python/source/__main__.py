from __future__ import annotations
import argparse
import logging
import multiprocessing
import pathlib
import pkgutil
import typing
from . import check
from . import configuration
from . import constants
from . import display
from . import formats
from . import install_mode
from . import task
from . import utilities

dirname = pathlib.Path(__file__).resolve().parent


def check_positive(value: str):
    value_as_int = int(value)
    if value_as_int <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return value_as_int


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--configuration",
        "-c",
        default="undr.toml",
        help="UNDR configuration file path",
    )
    parser.add_argument(
        "--timeout", "-t", default=None, type=float, help="Socket timeout in seconds"
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=check_positive,
        default=multiprocessing.cpu_count() * 2,
        help="Number of parallel processes",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Download server files even if they already exist locally",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download UNDR datasets listed on a configuration file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--log-directory", help="write log files to this directory")
    subparsers = parser.add_subparsers(dest="command")
    init_parser = subparsers.add_parser(
        "init", help="Generate a default undr.toml file"
    )
    init_parser.add_argument(
        "--configuration",
        "-c",
        default="undr.toml",
        help="UNDR configuration file path",
    )
    install_parser = subparsers.add_parser("install", help="Provision the datasets")
    add_common_arguments(install_parser)
    bibtex_parser = subparsers.add_parser(
        "bibtex", help="Generate a BibTeX file referencing all the datasets"
    )
    bibtex_parser.add_argument(
        "output", help="Path to output.bib or - to print to stdout"
    )
    add_common_arguments(bibtex_parser)
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Read all the files and check their invariants (timestamps order, spatial coordinates range...)",
    )
    add_common_arguments(doctor_parser)
    check_for_upload_parser = subparsers.add_parser(
        "check-for-upload",
        help="Inspect a directory before uploading it to an UNDR server",
    )
    check_for_upload_parser.add_argument("path", help="Path to the local directory")
    check_for_upload_parser.add_argument(
        "--delete-extra-files",
        "-d",
        action="store_true",
        help="Delete the files that are not listed in -index.json",
    )
    check_for_upload_parser.add_argument(
        "--format-index",
        "-i",
        action="store_true",
        help="Sort the entries in -index.json",
    )
    args = parser.parse_args()

    log_directory: typing.Optional[pathlib.Path] = None
    if args.log_directory is not None:
        log_directory = pathlib.Path(args.log_directory)
        log_directory.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_directory / "main.log"),
            encoding="utf-8",
            level=logging.DEBUG,
            format="%(asctime)s %(message)s",
        )

    if args.command == "init":
        target = pathlib.Path(args.configuration)
        if target.is_file():
            print(display.format_error(f"{target} already exists"))
        else:
            undr_default = pkgutil.get_data("undr", "undr_default.toml")
            assert undr_default is not None
            with open(target, "wb") as target_file:
                target_file.write(undr_default)

    if args.command == "install":
        undr_configuration = configuration.configuration_from_path(
            pathlib.Path(args.configuration)
        )
        if args.timeout is not None:
            for (
                dataset_settings
            ) in undr_configuration.name_to_dataset_settings.values():
                dataset_settings.timeout = args.timeout
        try:
            undr_configuration.install(
                show_display=True,
                workers=args.workers,
                force=args.force,
                log_directory=log_directory,
            )
        except KeyboardInterrupt:
            pass

    if args.command == "bibtex":
        undr_configuration = configuration.configuration_from_path(
            pathlib.Path(args.configuration)
        )
        if args.timeout is not None:
            for (
                dataset_settings
            ) in undr_configuration.name_to_dataset_settings.values():
                dataset_settings.timeout = args.timeout
        try:
            content = undr_configuration.bibtex(
                show_display=args.output != "-",
                workers=args.workers,
                force=args.force,
                log_directory=log_directory,
                bibtex_timeout=constants.DEFAULT_TIMEOUT
                if args.timeout is None
                else args.timeout,
            )
            if args.output == "-":
                print(content)
            else:
                with open(args.output, "w") as output:
                    output.write(content)
                print(f"bibliography written to {args.output}")
        except KeyboardInterrupt:
            pass

    if args.command == "doctor":
        undr_configuration = configuration.configuration_from_path(
            pathlib.Path(args.configuration)
        )
        if args.timeout is not None:
            for (
                dataset_settings
            ) in undr_configuration.name_to_dataset_settings.values():
                dataset_settings.timeout = args.timeout
        error: typing.Optional[check.Error] = None
        for message in undr_configuration.map(
            switch=formats.Switch(
                handle_aps=check.handle_aps,
                handle_dvs=check.handle_dvs,
                handle_imu=check.handle_imu,
                handle_other=check.handle_other,
            )
        ):
            error = message
            break
        if error is None:
            print(display.format_info("No errors detected"))
        else:
            print(display.format_error(f"{error.path_id}: {error.message}"))

    """
    if args.command == "check-for-upload":
        logger = progress.Printer()
        with logger.group(progress.Phase(0, 1, "check local directory")):
            try:
                directory = IndexedDirectory(
                    path=pathlib.Path(args.path),
                    own_doi=None,
                    server=server_factory(
                        url=f"{pathlib.Path(args.path).as_posix()}/",
                        timeout=default_timeout,
                        type="local",
                    ),
                    parent=None,
                    metadata={},
                )
                directory.provision(logger=progress.Quiet())
                check_for_upload(
                    directory,
                    delete_ds_store=args.delete_ds_store,
                    format_index=args.format_index,
                )
                try:
                    directory.download(
                        force=False, logger=progress.Quiet(), workers_count=1
                    )
                except FileNotFoundError as error:
                    raise Exception(
                        '"{}" not found (listed in "{}")'.format(
                            error, pathlib.Path(str(error)).parent / "-index.json"
                        )
                    )
                with logger.group(
                    progress.ProcessDirectory(
                        0, 1, pathlib.Path(args.path).name, directory
                    )
                ):
                    for _, results in directory.recursive_map(
                        logger=logger,
                        handle_aps_file=check_aps_file,
                        handle_dvs_file=check_dvs_file,
                        handle_imu_file=check_imu_file,
                        handle_other_file=check_other_file,
                        workers_count=args.workers_count,
                    ):
                        for file, errors in list(results):
                            for error in errors:
                                logger.error(f'{error} in "{file.path}"')
            except:
                logger.error(str(sys.exc_info()[1]))
                sys.exit(1)
        """
