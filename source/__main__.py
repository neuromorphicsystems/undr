import argparse
import pathlib
from . import Configuration

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download UNDR datasets listed in a configuration file')
    parser.add_argument('--configuration', default='undr.toml', help='Configuration file path')
    args = parser.parse_args()
    args.configuration = pathlib.Path(args.configuration)

    Configuration(args.configuration)
