"""Binary description of all formats using numpy dtypes."""

from __future__ import annotations

import numpy

DVS_DTYPE: numpy.dtype = numpy.dtype(
    [("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "<u1")]
)
"""Data type for DVS files.

Each event uses 13 bytes, with no padding between events. The fields are packed in the following order:

- ``t``: 8 bytes unsigned integer, little endian (timestamp in µs)
- ``x``: 2 bytes unsigned integer, little endian (pixel position in the x direction in the range [0, width - 1], 0 is left)
- ``y``: 2 bytes unsigned integer, little endian (pixel position in the y direction in the range [0, height - 1], 0 is bottom)
- ``p``: 1 byte unsigned integer (polarity, 0 is OFF, 1 is ON)
"""


def aps_dtype(width: int, height: int) -> numpy.dtype:
    """Data type for APS files.

    Each frame uses 56 + (width * height * 2) bytes, with no padding between frames. Fields that are not available (for instance if the sensor does not record the frame start) are set to the maximum possible value (for instance 2 ** 64 - 1 for 8 bytes integer). The fields are packed in the following order:

    - ``t``: 8 bytes unsigned integer, little endian (timestamp in µs)
    - ``begin_t``: 8 bytes unsigned integer, little endian (AEDAT4 doc?)
    - ``end_t``: 8 bytes unsigned integer, little endian (AEDAT4 doc?)
    - ``exposure_begin_t``: 8 bytes unsigned integer, little endian (AEDAT4 doc?)
    - ``exposure_end_t``: 8 bytes unsigned integer, little endian (AEDAT4 doc?)
    - ``format``: 8 bytes unsigned integer, little endian (AEDAT4 doc?)
    - ``width``: 2 bytes unsigned integer, little endian (frame width in pixels)
    - ``height``: 2 bytes unsigned integer, little endian (frame height in pixels)
    - ``offset_x``: 2 bytes signed integer, little endian (x offset in pixels, relative to the sensor left edge)
    - ``offset_y``: 2 bytes signed integer, little endian (y offset in pixels, relative to the sensor bottom edge)
    - ``pixels``: width * height * 2 bytes, packed little endian unsigned integers (luminance values)
    """
    return numpy.dtype(
        [
            ("t", "<u8"),
            ("begin_t", "<u8"),
            ("end_t", "<u8"),
            ("exposure_begin_t", "<u8"),
            ("exposure_end_t", "<u8"),
            ("format", "<u8"),
            ("width", "<u2"),
            ("height", "<u2"),
            ("offset_x", "<i2"),
            ("offset_y", "<i2"),
            ("pixels", (numpy.dtype("<u2"), (width, height))),
        ]
    )


IMU_DTYPE: numpy.dtype = numpy.dtype(
    [
        ("t", "<u8"),
        ("temperature", "<f4"),
        ("accelerometer_x", "<f4"),
        ("accelerometer_y", "<f4"),
        ("accelerometer_z", "<f4"),
        ("gyroscope_x", "<f4"),
        ("gyroscope_y", "<f4"),
        ("gyroscope_z", "<f4"),
        ("magnetometer_x", "<f4"),
        ("magnetometer_y", "<f4"),
        ("magnetometer_z", "<f4"),
    ]
)
"""Data type for IMU files.

Each IMU sample uses 48 bytes, with no padding between samples. Fields that are not available (for instance, if the IMU has no magnetometer) are set to :py:attr:`numpy.NAN`. The fields are packed in the following order:

- ``t``: 8 bytes unsigned integer, little endian (timestamp in µs)
- ``temperature``: single-precision floating point number (IEEE 754) ()
- ``accelerometer_x``: single-precision floating point number (IEEE 754) (x-axis acceleration in m/s²)
- ``accelerometer_y``: single-precision floating point number (IEEE 754) (y-axis acceleration in m/s²)
- ``accelerometer_z``: single-precision floating point number (IEEE 754) (z-axis acceleration in m/s²)
- ``gyroscope_x``: single-precision floating point number (IEEE 754) (x-axis angular velocity in AEDAT4 doc?)
- ``gyroscope_y``: single-precision floating point number (IEEE 754) (y-axis angular velocity in AEDAT4 doc?)
- ``gyroscope_z``: single-precision floating point number (IEEE 754) (z-axis angular velocity in AEDAT4 doc?)
- ``magnetometer_x``: single-precision floating point number (IEEE 754) (x-axis angular position in AEDAT4 doc?)
- ``magnetometer_y``: single-precision floating point number (IEEE 754) (y-axis angular position in AEDAT4 doc?)
- ``magnetometer_z``: single-precision floating point number (IEEE 754) (z-axis angular position in AEDAT4 doc?)
"""
