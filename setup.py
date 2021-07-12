import setuptools
import sys

if not "-h" in sys.argv and not "--help" in sys.argv and ("sdist" in sys.argv or "develop" in sys.argv):
    import shutil
    import pathlib

    dirname = pathlib.Path(__file__).resolve().parent
    shutil.rmtree(dirname / "undr", ignore_errors=True)
    shutil.copytree(dirname / "source", dirname / "undr")
    shutil.copyfile(dirname / "specification" / "undr_schema.json", dirname / "undr" / "undr_schema.json")
    shutil.copyfile(dirname / "specification" / "-index_schema.json", dirname / "undr" / "-index_schema.json")
    shutil.copyfile(dirname / "undr_default.toml", dirname / "undr" / "undr_default.toml")

with open("README.md") as file:
    long_description = file.read()

setuptools.setup(
    name="undr",
    version="0.0.8",
    url="https://github.com/neuromorphicsystems/undr",
    author="Alexandre Marcireau",
    author_email="alexandre.marcireau@gmail.com",
    description="Download and process Neuromorphic datasets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "jsonschema-rs>=0.9",
        "lzip>=1.0",
        "numpy>=1.20",
        "requests>=2.25",
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
