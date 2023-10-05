import sys

import version

sys.stdout.write(
    "".join(
        f"{line}\n"
        for line in (
            f"- app {version.version_to_string(version.app_version)} (see Assets below)",
            f"- python {version.version_to_string(version.python_version)} (https://pypi.org/project/undr/)",
            f"- rust {version.version_to_string(version.rust_version)} (https://crates.io/crates/undr/)",
        )
    )
)
