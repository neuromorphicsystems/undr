import json
import sys

import version

sys.stdout.write(
    "".join(
        f"{line}\n"
        for line in (
            f"- app v{version.version_to_string(version.app_version)} (see Assets below)",
            f"- python v{version.version_to_string(version.python_version)} (https://pypi.org/project/undr/)",
            f"- rust v{version.version_to_string(version.rust_version)} (https://crates.io/crates/undr/)",
        )
    )
)
