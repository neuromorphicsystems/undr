## Contribute

```sh
cd python
black . # format the source code (see https://github.com/psf/black)
pyright . #check types (see https://github.com/microsoft/pyright)
python3 -m pip install -e . # local installation
```

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
