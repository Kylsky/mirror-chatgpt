import gzip
import brotli
from io import BytesIO
from typing import BinaryIO, Union

class WriteCloserWrapper:
    def __init__(self, writer: BinaryIO):
        self.writer = writer

    def write(self, data: bytes) -> int:
        return self.writer.write(data)

    def close(self) -> None:
        # No-op close method
        pass

def wrap_reader(reader: BinaryIO, compress_type: str) -> Union[BinaryIO, gzip.GzipFile]:
    if compress_type == "gzip":
        return gzip.GzipFile(fileobj=reader)
    elif compress_type == "br":
        return BytesIO(brotli.decompress(reader.read()))
    return reader

def wrap_writer(writer: BinaryIO, compress_type: str) -> Union[BinaryIO, gzip.GzipFile]:
    if compress_type == "gzip":
        return gzip.GzipFile(fileobj=writer, mode='wb')
    elif compress_type == "br":
        return BrotliWriter(writer)
    return WriteCloserWrapper(writer)

class BrotliWriter:
    def __init__(self, writer: BinaryIO):
        self.writer = writer
        self.compressor = brotli.Compressor()

    def write(self, data: bytes) -> int:
        compressed = self.compressor.process(data)
        if compressed:
            return self.writer.write(compressed)
        return 0

    def close(self) -> None:
        final = self.compressor.finish()
        if final:
            self.writer.write(final)