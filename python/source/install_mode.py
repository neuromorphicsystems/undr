"""Installation strategies."""

from __future__ import annotations

import enum


class Mode(enum.Enum):
    """Download strategy for a dataset."""

    DISABLED = "disabled"
    """The dataset is ignored by all actions.
    """

    REMOTE = "remote"
    """Only download the dataset's index files.

    UNDR can process the dataset files as if they were locally available, by streaming them from the server. This option is particularly useful for large datasets that do not fit on the hard drive but it requires a fast internet connection since files are re-downloaded every time.
    """

    LOCAL = "local"
    """Download all the dataset files locally but do not decompress them.

    Most datasets are stored as Brotli archives (https://github.com/google/brotli/). UNDR stream-decompresses files before processing, making this option a good trade-off between disk usage and processing speed.
    """

    RAW = "raw"
    """Downloads all the dataset files locally and decompresses them.

    Decompressed files use a relatively inefficient plain binary file format. This option requires vast amounts of disk space (3 to 5 times as much as the Brotli archives). However, the plain binary format facilitates processing from languages such as Matlab or C++.
    """
