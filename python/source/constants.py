"""Constants used throughout the codebase."""

CHUNK_SIZE: int = 65536
"""Buffer size in bytes for file reads."""

CONSUMER_POLL_PERIOD: float = 0.1
"""Sleep duration for msssage readers."""

DECOMPRESS_SUFFIX: str = ".decompress"
"""Suffix indicating that a file is being decompressed."""

DEFAULT_TIMEOUT: float = 60.0
"""Server timeout, can be overriden in settings TOML files."""

DOWNLOAD_SUFFIX: str = ".download"
"""Suffix indicating that a file is being downloaded."""

LRU_CACHE_MAXSIZE: int = 128
"""Number of index files cached by the load function."""

SPEED_SAMPLES: int = 30
"""Number of samples used to smooth the speed measurement (sliding window)."""

STREAM_CHUNK_THRESHOLD: int = 64
"""Below this number, files are download in one chunk instead of several to boost performance."""

WORKER_POLL_PERIOD: float = 0.02
"""Sleep duration for wworkers when the task queue is empty."""
