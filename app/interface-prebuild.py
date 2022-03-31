import shutil
import pathlib

dirname = pathlib.Path(__file__).resolve().parent
shutil.rmtree(dirname / "interface" / "undr", ignore_errors=True)
shutil.rmtree(dirname / "interface" / "build", ignore_errors=True)
shutil.copytree(dirname.parent / "source", dirname / "interface" / "undr")
shutil.copyfile(
    dirname.parent / "specification" / "undr_schema.json",
    dirname / "interface" / "undr" / "undr_schema.json",
)
shutil.copyfile(
    dirname.parent / "specification" / "-index_schema.json",
    dirname / "interface" / "undr" / "-index_schema.json",
)
shutil.copyfile(
    dirname.parent / "undr_default.toml",
    dirname / "interface" / "undr" / "undr_default.toml",
)
