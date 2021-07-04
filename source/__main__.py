import argparse
import pathlib
from . import Configuration, Dataset

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download UNDR datasets listed in a configuration file")
    parser.add_argument("--configuration", default="undr.toml", help="UNDR configuration file path")
    parser.add_argument("--timeout", default=10.0, type=float, help="Socket timeout in seconds")
    parser.add_argument("--force", action="store_true", help="(Re-)download files even if they already exist locally")
    args = parser.parse_args()

    configuration = Configuration(pathlib.Path(args.configuration), provision=False)
    for dataset in configuration.datasets.values():
        dataset.set_timeout(args.timeout)
    configuration.provision(force=args.force)
