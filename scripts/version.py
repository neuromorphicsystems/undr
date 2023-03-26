import json
import pathlib
import re
import tomllib

dirname = pathlib.Path(__file__).resolve().parent

VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def string_to_version(string: str) -> tuple[int, int, int]:
    version_match = VERSION_PATTERN.match(string)
    if version_match is None:
        sys.stderr.write(f"{string} did not match the expected version pattern")
        sys.exit(1)
    return (int(version_match[1]), int(version_match[2]), int(version_match[3]))


def version_to_string(version: tuple[int, int, int]):
    return f"{version[0]}.{version[1]}.{version[2]}"


with open(dirname.parent / "app" / "src-tauri" / "tauri.conf.json") as tauri_file:
    tauri = json.load(tauri_file)
app_version = string_to_version(tauri["package"]["version"])
with open(dirname.parent / "app" / "src-tauri" / "Cargo.toml", "rb") as cargo_file:
    app_version_cargo = string_to_version(
        tomllib.load(cargo_file)["package"]["version"]
    )
    if tomllib.load(cargo_file)["package"]["version"] != app_version:
        sys.stderr.write(
            f'mismatched versions in "app/src-tauri/tauri.conf.json" and "app/src-tauri/Cargo.toml" ({app_version} and {app_version_cargo})'
        )
        sys.exit(1)

exec(
    open(dirname.parent / "python" / "source" / "version.py").read()
)  # defines __version__
python_version = string_to_version(__version__)  # type: ignore

with open(dirname.parent / "rust" / "Cargo.toml", "rb") as cargo_file:
    cargo = tomllib.load(cargo_file)
rust_version = string_to_version(cargo["package"]["version"])

maximum_version = max(app_version, python_version, rust_version)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--maximum", action="store_true")
    args = parser.parse_args()
    if args.maximum:
        sys.stdout.write(version_to_string(maximum_version))
        sys.exit(0)
    sys.stdout.write(
        json.dumps(
            {
                "app": version_to_string(app_version),
                "python": version_to_string(python_version),
                "rust": version_to_string(rust_version),
            },
            separators=(",", ":"),
        )
    )
    sys.exit(0)
