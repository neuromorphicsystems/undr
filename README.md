<p align="center">
    <img src="https://raw.githubusercontent.com/neuromorphicsystems/undr/main/undr.png" width="256">
</p>

**Unified Neuromorphic Datasets Repository** (UNDR) is a tool that makes it easy to download and analyse a large number of Neuromorphic datasets.

Specifically, UNDR:

-   defines a standard format to store Neuromorphic datasets.
-   re-destributes as many datasets as possible, encoded in the aforementioned format.
-   provides a graphical app, command-line tools, and libraries (Python and Rust) to download the datasets.
-   provides a Python library to implement parallel processing algorithms.

## Links for users

-   **Browse datasets online**: https://www.undr.space
-   **Download the app**: https://github.com/neuromorphicsystems/undr/releases
-   **Python documentation**: https://neuromorphicsystems.github.io/undr/
-   **Rust documentation**: https://docs.rs/undr/0.2.0/undr/

## Links for datasets creators

-   **Self-hosting guide**: https://neuromorphicsystems.github.io/undr/
-   **AWS S3 hosting guide**: https://neuromorphicsystems.github.io/undr/
-   **Converting a dataset to UNDR**: https://github.com/neuromorphicsystems/undrdg
-   **UNDR format specification**: https://neuromorphicsystems.github.io/undr/

## Contribute

### Graphical app

See [app/README.md](app/README.md) for build instructions.

### Online dataset browser

See [aws/README.md](aws/README.md) for build instructions.

### Documentation

```sh
python3 -m venv .venv
source .venv/bin/activate
python documentation/build.py
```

The documentation is generated in _documentation/\_build_ and the entry point is _documentation/\_build/index.html_.

### Python

See [python/README.md](python/README.md) for build instructions.

### Rust

See [rust/README.md](rust/README.md) for build instructions.

### Scripts

The Python scripts in the top-level [scripts](scripts) directory extract version numbers to generate GitHub releases. Python scripts that download or analyse datasets can be found in [python/examples](python/examples).

### Specification

The top-level [specification](specification) directory contains the JSON schemas at the heart of the UNDR format specification. The full specification includes a few rules that are not enforced by the schemas (due to limitations of JSON schema implementations at the time of writing) and a description of binary encodings. See https://neuromorphicsystems.github.io/undr/ for details.
