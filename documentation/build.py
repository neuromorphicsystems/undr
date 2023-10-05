import pathlib
import shutil
import subprocess
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
    cwd=dirname.parent,
)

shutil.rmtree(dirname / "_build", ignore_errors=True)

subprocess.check_call(
    args=[
        "sphinx-build",
        "documentation",
        str(dirname / "_build"),
    ],
    cwd=dirname.parent,
)
