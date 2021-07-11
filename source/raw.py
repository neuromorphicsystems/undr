import functools
import types
import numpy

def aps_dtype(width, height):
    return [
        ('t', '<u8'),
        ('begin_t', '<u8'),
        ('end_t', '<u8'),
        ('exposure_begin_t', '<u8'),
        ('exposure_end_t', '<u8'),
        ('format', '<u8'),
        ('width', '<u2'),
        ('height', '<u2'),
        ('offset_x', '<i2'),
        ('offset_y', '<i2'),
        ('pixels', (numpy.dtype('<u2'), (width, height))),
    ]

for name, dtype in (
    ('dvs', [('t', '<u8'), ('x', '<u2'), ('y', '<u2'), ('p', '<u1')]),
    ('aps_240_180', aps_dtype(240, 180)),
    ('imu', [
        ('t', '<u8'),
        ('temperature', '<f4'),
        ('accelerometer_x', '<f4'),
        ('accelerometer_y', '<f4'),
        ('accelerometer_z', '<f4'),
        ('gyroscope_x', '<f4'),
        ('gyroscope_y', '<f4'),
        ('gyroscope_z', '<f4'),
        ('magnetometer_x', '<f4'),
        ('magnetometer_y', '<f4'),
        ('magnetometer_z', '<f4'),
    ]),
):
    namespace = types.SimpleNamespace()
    globals()[name] = namespace
    namespace.dtype = numpy.dtype(dtype)
    namespace.zeros = functools.partial(numpy.zeros, dtype=namespace.dtype)
    namespace.fromfile = functools.partial(numpy.fromfile, dtype=namespace.dtype)
    namespace.frombuffer = functools.partial(numpy.frombuffer, dtype=namespace.dtype)
