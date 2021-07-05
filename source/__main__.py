import argparse
import pathlib
import shutil
from . import Configuration

dirname = pathlib.Path(__file__).resolve().parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download UNDR datasets listed in a configuration file")
    subparsers = parser.add_subparsers(dest="command")
    init_parser = subparsers.add_parser("init", help="Generate a default undr.toml file")
    init_parser.add_argument("--configuration", default="undr.toml", help="UNDR configuration file path")
    install_parser = subparsers.add_parser("install", help="Provision the datasets")
    install_parser.add_argument("--configuration", default="undr.toml", help="UNDR configuration file path")
    install_parser.add_argument("--timeout", default=10.0, type=float, help="Socket timeout in seconds")
    install_parser.add_argument(
        "--force", action="store_true", help="(Re-)download files even if they already exist locally"
    )
    bibtex_parser = subparsers.add_parser("bibtex", help="Generate a BibTeX referencing all the datasets")
    bibtex_parser.add_argument("--configuration", default="undr.toml", help="UNDR configuration file path")
    bibtex_parser.add_argument("--timeout", default=10.0, type=float, help="Socket timeout in seconds")
    bibtex_parser.add_argument("--output", default=None, help="Specify an output file (defaults to standard output)")
    args = parser.parse_args()

    if args.command == "init":
        target = pathlib.Path(args.configuration)
        if target.is_file():
            print(f"{target} already exists")
        else:
            shutil.copyfile(dirname / "undr_default.toml", target)

    if args.command == "install":
        configuration = Configuration(pathlib.Path(args.configuration), provision=False)
        for dataset in configuration.datasets.values():
            dataset.set_timeout(args.timeout)
        configuration.provision(force=args.force, quiet=False)

    if args.command == "bibtex":
        configuration = Configuration(pathlib.Path(args.configuration), provision=False)
        for dataset in configuration.datasets.values():
            dataset.set_timeout(args.timeout)
            dataset.mode = "remote"
        configuration.provision(force=False, quiet=True)
        bibtex = configuration.bibtex(pretty=True, timeout=args.timeout)
        if args.output is None:
            print(bibtex)
        else:
            with open(args.output, "wb") as bibtex_file:
                bibtex_file.write(bibtex.encode())
