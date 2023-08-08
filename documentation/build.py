import pathlib
import subprocess
import shutil
import sys

dirname = pathlib.Path(__file__).resolve().parent

subprocess.check_call(
    args=[sys.executable, "-m", "pip", "install", "."],
    cwd=dirname.parent / "python",
)

subprocess.check_call(
    args=[
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(dirname / "requirements.txt"),
    ],
)

shutil.rmtree(dirname / "_build", ignore_errors=True)

subprocess.check_call(
    args=[
        str(dirname.parent / ".venv" / "bin" / "sphinx-build"),
        "documentation",
        str(dirname / "_build"),
    ]
)
