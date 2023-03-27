from __future__ import annotations

import numpy

DVS_DTYPE = numpy.dtype([("t", "<u8"), ("x", "<u2"), ("y", "<u2"), ("p", "<u1")])


def aps_dtype(width: int, height: int):
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


IMU_DTYPE = numpy.dtype(
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
