from __future__ import annotations

import argparse
import logging
import multiprocessing
import pathlib
import pkgutil
import sys
import typing

from . import (
    check,
    configuration,
    constants,
    display,
    formats,
    install_mode,
    json_index_tasks,
    remote,
    task,
)

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
    check_conformance_parser = subparsers.add_parser(
        "check-conformance",
        help="Inspect a directory before uploading it to an UNDR server",
    )
    check_conformance_parser.add_argument("path", help="Path to the local directory")
    check_conformance_parser.add_argument(
        "--skip-format-index",
        "-s",
        action="store_true",
        help="Do not format -index.json files",
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

    if args.command == "check-conformance":
        conformance_error: typing.Optional[str] = None
        try:
            path = pathlib.Path(args.path)
            check.structure_recursive(path)
            index_status = configuration.IndexStatus(
                dataset_settings=None,  # type: ignore
                current_index_files=0,
                final_index_files=1,
                server=remote.NullServer(),
                selector=json_index_tasks.Selector(),
                downloaded_and_processed=True,
            )
            with display.Display(
                statuses=[
                    display.Status.from_path_id_and_mode(
                        path_id=pathlib.PurePosixPath(path.name),
                        dataset_mode=install_mode.Mode.RAW,
                    ),
                ],
                output_interval=constants.CONSUMER_POLL_PERIOD,
                download_speed_samples=constants.SPEED_SAMPLES,
                process_speed_samples=constants.SPEED_SAMPLES,
                download_tag=display.Tag(label="download", icon="↓"),
                process_tag=display.Tag(label="process", icon="⚛"),
            ) as terminal_display, task.ProcessManager() as manager:
                manager.schedule(
                    task=json_index_tasks.Index(
                        path_root=path.parent,
                        path_id=pathlib.PurePosixPath(path.name),
                        server=index_status.server,
                        selector=json_index_tasks.Selector(),
                        priority=0,
                        force=False,
                        directory_doi=False,
                    ),
                    priority=0,
                )
                for message in manager.messages():
                    if isinstance(message, task.Exception):
                        raise Exception(str(message.traceback_exception))
                    terminal_display.push(message)
                    indexing_complete, status = index_status.push(message=message)
                    if indexing_complete and status is not None:
                        manager.schedule(
                            task=json_index_tasks.CheckLocalDirectoryRecursive(
                                path_root=path.parent,
                                path_id=pathlib.PurePosixPath(path.name),
                                switch=formats.Switch(
                                    handle_aps=check.handle_aps,
                                    handle_dvs=check.handle_dvs,
                                    handle_imu=check.handle_imu,
                                    handle_other=check.handle_other,
                                ),
                                priority=1,
                            ),
                            priority=1,
                        )
            if not args.skip_format_index:
                check.format_index_recursive(
                    path=path,
                    handle_path=lambda path: print(
                        display.format_info(f"Formatted {path}")
                    ),
                )
        except KeyboardInterrupt:
            conformance_error = "Interrupted"
        except:
            conformance_error = str(sys.exc_info()[1])
        if conformance_error is None:
            print(display.format_info("No errors detected"))
        else:
            print(display.format_error(conformance_error))
