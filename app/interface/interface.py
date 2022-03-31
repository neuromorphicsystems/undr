from __future__ import annotations
import copy
import json
import pathlib
import pkgutil
import re
import struct
import sys
import typing
import undr

action_to_arguments = {
    "init": {
        "options": {},
        "flags": {},
    },
    "install": {
        "options": {
            "timeout": {"parser": float, "value": 60},
            "workers_count": {"parser": int, "value": 32},
        },
        "flags": {
            "force": {
                "value": False,
            },
        },
    },
    "bibtex": {
        "options": {
            "timeout": {"parser": float, "value": 60},
            "workers_count": {"parser": int, "value": 32},
            "output": {"parser": str, "value": None},
        },
        "flags": {},
    },
}

option_pattern = re.compile(r"^--(\w+)=(.*)$")

flag_pattern = re.compile(r"^--(\w+)$")


def output(data: typing.Any) -> None:
    message = json.dumps(data, separators=(",", ":"))
    sys.stdout.buffer.write(struct.pack("<Q", len(message)) + message.encode())
    sys.stdout.flush()


class Logger(undr.progress.Logger):
    def __init__(
        self,
        root: pathlib.Path,
        output_interval: float = 0.1,
        speed_samples_count: int = constants.SPEED_SAMPLES,
    ):
        self.root = root
        super().__init__(
            output_interval=output_interval, speed_samples_count=speed_samples_count
        )

    def group_begin(self, group: undr.progress.Group) -> None:
        if type(group) == undr.progress.Phase:
            output(
                {
                    "type": "group_begin",
                    "group": "phase",
                    "index": group.index,
                    "count": group.count,
                    "name": group.name,
                }
            )
        elif type(group) == undr.progress.ProcessDirectory:
            output(
                {
                    "type": "group_begin",
                    "group": "process_directory",
                    "index": group.index,
                    "count": group.count,
                    "name": group.name,
                    "directory": group.directory.path.relative_to(self.root).as_posix(),
                }
            )

    def group_end(self, group: undr.progress.Group) -> None:
        if type(group) == undr.progress.Phase:
            output(
                {
                    "type": "group_end",
                    "group": "phase",
                    "name": group.name,
                }
            )
        elif type(group) == undr.progress.ProcessDirectory:
            output(
                {
                    "type": "group_end",
                    "group": "process_directory",
                    "index": group.index,
                    "count": group.count,
                    "name": group.name,
                    "directory": group.directory.path.relative_to(self.root).as_posix(),
                    "files": None
                    if (
                        group.directory.files is None
                        or group.directory.other_files is None
                    )
                    else (
                        len(group.directory.files) + len(group.directory.other_files)
                    ),
                }
            )

    def output(self, status: undr.progress.Status, speed: float) -> None:
        output(
            {
                "type": "progress",
                "todo_file_count": status.todo_file_count,
                "done_file_count": status.done_file_count,
                "todo_size": status.todo_size,
                "done_size": status.done_size,
                "speed": speed,
            }
        )

    def error(self, message: str) -> None:
        output(
            {
                "type": "error",
                "message": message,
            }
        )


try:
    if len(sys.argv) < 3:
        raise Exception("usage: interface /path/to/undr.toml action [options] [flags]")
    target = pathlib.Path(sys.argv[1]).resolve()
    action = sys.argv[2]
    if not action in action_to_arguments:
        raise Exception(
            "unknown action {}, must be in {{{}}}".format(
                action, ", ".join(action_to_arguments.keys())
            )
        )
    arguments = copy.deepcopy(action_to_arguments[action])
    for argument in sys.argv[3:]:
        flag_match = flag_pattern.match(argument)
        if flag_match is None:
            option_match = option_pattern.match(argument)
            if option_match is None:
                raise Exception(f"expected an option or flag, got {argument}")
            else:
                option = option_match.group(1)
                if not option in arguments["options"]:
                    raise Exception(
                        "unknown option --{} for action {{{}}}".format(
                            option, action, ", ".join(arguments["options"].keys())
                        )
                    )
                arguments["options"][option]["value"] = arguments["options"][option][
                    "parser"
                ](option_match.group(2))
        else:
            flag = flag_match.group(1)
            if not flag in arguments["flags"]:
                raise Exception(
                    "unknown flag --{} for action {}, must be in {{{}}}".format(
                        flag, action, ", ".join(arguments["flags"].keys())
                    )
                )
            arguments["flags"][flag]["value"] = True
    if action == "init":
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            undr_default = pkgutil.get_data("undr", "undr_default.toml")
            with open(target, "wb") as target_file:
                target_file.write(undr_default)
        configuration = undr.Configuration(target)
        output(
            {
                "type": "init",
                "datasets": [
                    {
                        "name": name,
                        "url": dataset.url,
                        "mode": dataset.mode,
                        "server_type": dataset.server_type,
                    }
                    for name, dataset in configuration.datasets.items()
                ],
            }
        )
        # @DEV init should also read local files
    if action == "install":
        configuration = undr.Configuration(target)
        for dataset in configuration.datasets.values():
            dataset.set_timeout(
                arguments["options"]["timeout"]["value"], recursive=True
            )
        configuration.install(
            force=arguments["flags"]["force"]["value"],
            logger=Logger(configuration.directory),
            workers_count=arguments["options"]["workers_count"]["value"],
        )
    if action == "bibtex":
        configuration = undr.Configuration(target)
        count_offset = 0
        for dataset in configuration.datasets.values():
            if dataset.mode != "disabled":
                dataset.set_timeout(
                    arguments["options"]["timeout"]["value"], recursive=True
                )
                object.__setattr__(dataset, "mode", "remote")
                count_offset = 1
        logger = Logger(configuration.directory)
        logger.set_phase_offsets(index=0, count=count_offset)
        configuration.install(
            force=False,
            logger=logger,
            workers_count=arguments["options"]["workers_count"]["value"],
        )
        with logger.group(undr.progress.Phase(count_offset, 1, "download references")):
            bibtex = configuration.bibtex(
                pretty=True, timeout=arguments["options"]["timeout"]["value"]
            )
            if arguments["options"]["output"]["value"] is None:
                raise Exception(
                    "the option --output is required with the bibtex action"
                )
            with open(arguments["options"]["output"]["value"], "wb") as bibtex_file:
                bibtex_file.write(bibtex.encode())
except KeyboardInterrupt:
    pass
except:
    output(
        {
            "type": "error",
            "message": str(sys.exc_info()[1]),
        }
    )
    # @DEV {
    with open("interface_error.log", "w") as file:
        file.write(str(sys.exc_info()))
        file.write(str(sys.exc_info()[1]) + "\n")
        import traceback

        traceback.print_tb(sys.exc_info()[2], file=file)
    # }
