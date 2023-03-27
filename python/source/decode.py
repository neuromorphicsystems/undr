from __future__ import annotations

import dataclasses
import pathlib
import typing

import requests

from . import constants, task, utilities


@dataclasses.dataclass
class Progress:
    path_id: pathlib.PurePosixPath
    initial_bytes: int
    current_bytes: int
    final_bytes: int
    complete: bool


class RemainingBytesError(Exception):
    def __init__(self, word_size: int, buffer: bytes):
        self.buffer = buffer
        super().__init__(
            f"The total number of bytes is not a multiple of {word_size} ({len(buffer)} remaining)"
        )


class Decoder:
    def decompress(self, buffer: bytes) -> bytes:
        raise NotImplementedError()

    def finish(self) -> tuple[bytes, bytes]:
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True)
class Compression:
    suffix: str
    size: int
    hash: str

    def decoder(self, word_size: int) -> Decoder:
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True)
class NoneCompression(Compression):
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
                raise Exception("the Brotli decoded expected more data")
            return super().finish()

    def decoder(self, word_size: int):
        return BrotliCompression.Decoder(word_size=word_size)


class DecompressFile(task.Task):
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
            raise Exception(
                f'bad size for "{self.path_id}" (expected "{self.expected_size}", got "{size}")'
            )
        digest = hash.hexdigest()
        if digest != self.expected_hash:
            raise Exception(
                f'bad hash for "{self.path_id}" (expected "{self.expected_hash}", got "{digest}")'
            )
        decompress_path.rename(self.path_root / self.path_id)
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


def compression_from_dict(data: dict[str, typing.Any], base_size: int, base_hash: str):
    if data["type"] == "none":
        return NoneCompression(suffix=data["suffix"], size=base_size, hash=base_hash)
    if data["type"] == "brotli":
        return BrotliCompression(
            suffix=data["suffix"], size=data["size"], hash=data["hash"]
        )
    raise RuntimeError("unsupported compression type {}".format(data["type"]))
