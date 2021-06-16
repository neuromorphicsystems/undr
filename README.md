<p align="center">
    <img src="https://raw.githubusercontent.com/neuromorphicsystems/undr/main/undr.png" width="256">
</p>

# Unified Neuromorphic Datasets Repository

- [Python package](#python-package)
- [Dataset format specification](#dataset-format-specification)
- [Dataset mirrors](#dataset-mirrors)

## Python package

```sh
pip3 install undr
```

## Dataset format specification

## Dataset mirrors

## Publish

1. Bump the version number in *setup.py*.

2. Install twine
```
pip3 install twine
```

3. Upload the source code to PyPI:
```
rm -rf dist
python3 setup.py sdist
python3 -m twine upload dist/*
```
