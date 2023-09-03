from __future__ import annotations

import dataclasses
import exception
import pathlib
import typing

import requests

from . import constants, task, utilities


@dataclasses.dataclass
class Progress:
    """Represents decompression progress for a given resource."""

    path_id: pathlib.PurePosixPath
    """Identifier of the resource.
    """

    initial_bytes: int
    """Number of bytes of the decompressed resource that were already decompressed when the current decoding process began.
    """

    current_bytes: int
    """Number of bytes of the decompressed resource that have been decompressed so far.
    """

    final_bytes: int
    """Total number of bytes of the decompressed resource.
    """

    complete: bool
    """Whether decoding of this resource is complete.
    """


class RemainingBytesError(Exception):
    """Raised if the number of bytes in the decompressed resource is not a multiple of its word size.

    Args:
        word_size (int): The resource's word size.
        buffer (bytes): The remaining bytes. Their length is larger than zero and smaller than the word size.
    """

    def __init__(self, word_size: int, buffer: bytes):
        self.buffer = buffer
        super().__init__(
            f"The total number of bytes is not a multiple of {word_size} ({len(buffer)} remaining)"
        )


class Decoder:
    """Abstract class for decoders. A decoder controls a decompression process."""

    def decompress(self, buffer: bytes) -> bytes:
        """Consumes a buffer and produces decompressed bytes.

        Args:
            buffer (bytes): Compressed input bytes.

        Returns:
            bytes: Decompressed output bytes. Their length must be a multiple of the word size.
        """
        raise NotImplementedError()

    def finish(self) -> tuple[bytes, bytes]:
        """Tells the decoder that all input bytes have been read.

        Returns:
            tuple[bytes, bytes]: Decompressed output bytes, whose length must be a multiple of the word size, and remaining bytes, whose length must be striclty smaller than the word size. A non-zero number of remaining bytes usually indicates an issue (erroneous configuration or corrupted data).
        """
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True)
class Compression:
    """Represents a compressed file's metadata."""

    suffix: str
    """Suffix for files compressed with this format.

    The suffix must include a leading dot, for instance ``".br"``.
    """

    size: int
    """Size of the compressed file in bytes.
    """

    hash: str
    """SHA3-224 (FIPS 202) hash of the compressed bytes.
    """

    def decoder(self, word_size: int) -> Decoder:
        """Creates a new decoder for this compression.

        Args:
            word_size (int): The resource's word size in bytes.

        Returns:
            Decoder: A decompression manager for this compression format.
        """
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True)
class NoneCompression(Compression):
    """Placeholder format for uncompressed files.

    This "compression" format passes the input bytes to the output without transforming them.
    It may cut and stitch buffers to ensure that each buffer has a length that is a multiple of the word size.

    Args:
        word_size (int): The resource's word size in bytes.
    """

    class Decoder(Decoder):
        def __init__(self, word_size: int):
            assert word_size > 0
            self.word_size = word_size
            self.buffer = bytes()

        def decompress(self, buffer: bytes):
            if len(self.buffer) == 0:
                if len(buffer) % self.word_size == 0:
                    return buffer
                else:
                    remaning_bytes_count = len(buffer) % self.word_size
                    buffer, self.buffer = (
                        buffer[0 : len(self.buffer) - remaning_bytes_count],
                        buffer[len(buffer) - remaning_bytes_count :],
                    )
                    return buffer
            remaning_bytes_count = (len(self.buffer) + len(buffer)) % self.word_size
            if remaning_bytes_count == 0:
                buffer, self.buffer = self.buffer + buffer, bytes()
                return buffer
            if remaning_bytes_count < len(buffer):
                buffer, self.buffer = (
                    self.buffer + buffer[0 : len(buffer) - remaning_bytes_count],
                    buffer[len(buffer) - remaning_bytes_count :],
                )
                return buffer
            if remaning_bytes_count == len(buffer):
                buffer, self.buffer = self.buffer, buffer
                return buffer
            buffer, self.buffer = (
                self.buffer[0 : len(self.buffer) + len(buffer) - remaning_bytes_count],
                self.buffer[len(self.buffer) + len(buffer) - remaning_bytes_count :]
                + buffer,
            )
            return buffer

        def finish(self):
            remaning_bytes_count = len(self.buffer) % self.word_size
            return (
                self.buffer[0 : len(self.buffer) - remaning_bytes_count],
                self.buffer[len(self.buffer) - remaning_bytes_count :],
            )

    def decoder(self, word_size: int):
        return NoneCompression.Decoder(word_size=word_size)


@dataclasses.dataclass(frozen=True)
class BrotliCompression(Compression):
    """Implements Brotli decompression (https://github.com/google/brotli).

    Args:
        word_size (int): The resource's word size in bytes.
    """

    class Decoder(NoneCompression.Decoder):
        def __init__(self, word_size: int):
            super().__init__(word_size=word_size)
            import brotli

            self.decoder = brotli.Decompressor()

        def decompress(self, buffer: bytes):
            decompressed_bytes = self.decoder.process(buffer)

            return super().decompress(decompressed_bytes)

        def finish(self):
            if not self.decoder.is_finished():
                raise Exception("the Brotli decoder expected more data")
            return super().finish()

    def decoder(self, word_size: int):
        return BrotliCompression.Decoder(word_size=word_size)


class DecompressFile(task.Task):
    """Decompresses a local file and writes decoded bytes to another local file.

    Args:
        path_root (pathlib.Path): The root path used to generate local file paths.
        path_id (pathlib.PurePosixPath): The path ID of the file.
        compression (Compression): The format of the compressed file.
        expected_size (int): The size of the decompressed file in bytes, according to the index.
        expected_hash (str): The hash of the decompressed file, according to the index.
        word_size (int): The file's word size (the number of decoded bytes must be a multiple of this value).
        keep (bool): Whether to keep the compressed file after a successful decompression.
    """

    def __init__(
        self,
        path_root: pathlib.Path,
        path_id: pathlib.PurePosixPath,
        compression: Compression,
        expected_size: int,
        expected_hash: str,
        word_size: int,
        keep: bool,
    ):
        self.path_root = path_root
        self.path_id = path_id
        self.compression = compression
        self.expected_size = expected_size
        self.expected_hash = expected_hash
        self.word_size = word_size
        self.keep = keep

    def run(self, session: requests.Session, manager: task.Manager):
        hash = utilities.new_hash()
        decompress_path = utilities.path_with_suffix(
            self.path_root / self.path_id, constants.DECOMPRESS_SUFFIX
        )
        with open(
            utilities.path_with_suffix(
                self.path_root / self.path_id, self.compression.suffix
            ),
            "rb",
        ) as compressed_file:
            with open(decompress_path, "wb") as decompressed_file:
                decoder = self.compression.decoder(word_size=self.word_size)
                while True:
                    compressed_buffer = compressed_file.read(constants.CHUNK_SIZE)
                    if len(compressed_buffer) == 0:
                        break
                    decompressed_buffer = decoder.decompress(compressed_buffer)
                    decompressed_file.write(decompressed_buffer)
                    hash.update(decompressed_buffer)
                    manager.send_message(
                        Progress(
                            path_id=self.path_id,
                            initial_bytes=0,
                            current_bytes=len(decompressed_buffer),
                            final_bytes=len(decompressed_buffer),
                            complete=False,
                        )
                    )
                (decompressed_buffer, remaining_bytes) = decoder.finish()
                decompressed_file.write(decompressed_buffer)
                hash.update(decompressed_buffer)
                manager.send_message(
                    Progress(
                        path_id=self.path_id,
                        initial_bytes=0,
                        current_bytes=len(decompressed_buffer),
                        final_bytes=len(decompressed_buffer),
                        complete=False,
                    )
                )
                if len(remaining_bytes) > 0:
                    raise RemainingBytesError(
                        word_size=self.word_size, buffer=remaining_bytes
                    )
        size = decompress_path.stat().st_size
        if size != self.expected_size:
            raise exception.SizeMismatch(self.path_id, self.expected_size, size)
        digest = hash.hexdigest()
        if digest != self.expected_hash:
            exception.HashMismatch(self.path_id, self.expected_hash, digest)
        decompress_path.replace(self.path_root / self.path_id)
        if not self.keep:
            utilities.path_with_suffix(
                self.path_root / self.path_id, self.compression.suffix
            ).unlink()
        manager.send_message(
            Progress(
                path_id=self.path_id,
                initial_bytes=0,
                current_bytes=0,
                final_bytes=0,
                complete=True,
            )
        )


def compression_from_dict(
    data: dict[str, typing.Any], base_size: int, base_hash: str
) -> Compression:
    """Factory for comprssion formats.

    Args:
        data (dict[str, typing.Any]): Parsed compression object read from an index file.
        base_size (int): Size of the uncompressed file in bytes, read from the index.
        base_hash (str): Hash of the uncompressed file, read from the index.

    Raises:
        RuntimeError: if the compression format is unknown or not supported.

    Returns:
        Compression: The compressed file's metadata, can be used to create a decoder.
    """
    if data["type"] == "none":
        return NoneCompression(suffix=data["suffix"], size=base_size, hash=base_hash)
    if data["type"] == "brotli":
        return BrotliCompression(
            suffix=data["suffix"], size=data["size"], hash=data["hash"]
        )
    raise RuntimeError("unsupported compression type {}".format(data["type"]))
