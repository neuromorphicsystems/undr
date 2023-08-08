import pathlib


class HashMismatch(Exception):
    """Raised if the hash read from the index is different from the hash calculated from the file bytes.

    Args:
        path_id (pathlib.PurePosixPath): The path ID of the resource with a hash mismatch.
        expected_hash (str): The hash read from the index.
        hash (str): The hash calculated from the bytes effectively processed.
    """

    def __init__(self, path_id: pathlib.PurePosixPath, expected_hash: str, hash: str):
        super().__init__(
            f'hash mismatch for "{path_id}" (expected "{expected_hash}", got "{hash}")'
        )


class SizeMismatch(Exception):
    """Raised if the size read from the index is different from number of bytes in the decompressed file.

    Args:
        path_id (pathlib.PurePosixPath): The path ID of the resource with a size mismatch.
        expected_size (int): The size read from the index.
        size (int): The effective decompressed size in bytes.
    """

    def __init__(self, path_id: pathlib.PurePosixPath, expected_size: int, size: int):
        super().__init__(
            f'size mistmatch for "{path_id}" (expected "{expected_size}", got "{size}")'
        )
