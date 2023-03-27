import pathlib
import sys

import setuptools

dirname = pathlib.Path(__file__).resolve().parent

if (
    not "-h" in sys.argv
    and not "--help" in sys.argv
    and ("sdist" in sys.argv or "develop" in sys.argv)
):
    import shutil

    shutil.rmtree(dirname / "undr", ignore_errors=True)
    shutil.copytree(dirname / "source", dirname / "undr")
    shutil.copyfile(
        dirname.parent / "specification" / "undr_schema.json",
        dirname / "undr" / "undr_schema.json",
    )
    shutil.copyfile(
        dirname.parent / "specification" / "-index_schema.json",
        dirname / "undr" / "-index_schema.json",
    )
    shutil.copyfile(
        dirname.parent / "undr_default.toml", dirname / "undr" / "undr_default.toml"
    )
    shutil.copyfile(dirname.parent / "README.md", dirname / "long_description.md")

with open(dirname / "long_description.md") as long_description_file:
    long_description = long_description_file.read()

exec(open(dirname / "undr" / "version.py").read())  # defines __version__

setuptools.setup(
    name="undr",
    version=__version__,  # type: ignore
    url="https://github.com/neuromorphicsystems/undr",
    author="Alexandre Marcireau",
    author_email="alexandre.marcireau@gmail.com",
    description="Download and process Neuromorphic datasets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "brotli>=1.0,<2",
        "jsonschema-rs>=0.16",
        "numpy>=1.24,<2",
        "requests>=2.28,<3",
        "toml>=0.10",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    packages=["undr"],
    package_data={"": ["*.json", "*.toml"]},
)
