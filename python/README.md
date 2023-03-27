## Contribute

```sh
cd python
python3 setup.py develop
isort . # sort imports (see https://github.com/PyCQA/isort)
black . # format the source code (see https://github.com/psf/black)
pyright . #check types (see https://github.com/microsoft/pyright)
```

To uninstall the local development version, run `python3 setup.py develop --uninstall`

### Publish the module

1. Bump the version number in _setup.py_.

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
