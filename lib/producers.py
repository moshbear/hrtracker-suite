# hrtracker-suite
#
# Copyright (c) 2020 Andrey V
# All rights reserved.
#
# This code is licensed under the 3-clause BSD License.
# See the LICENSE file at the root of this project.

from datetime import datetime
import re
from .types import HRTrackerData, Datum

__all__ = ['CannotDecodeFileException', 'decode_stream']

# fitdecode is only needed for fit file decoding; we can limp along with
# just pnn-sgt
try:
    import fitdecode
except ImportError:
    fitdecode = None

class CannotDecodeFileException(Exception):
    pass

def decode_stream(stream, filename = None):
    """
    Decode a stream given a file-ish and an optional filename. 
    The returned decoder is a generator that yields `Datum`s.
    Raise `CannotDecodeFileException` if no suitable decoder found.
    """
    first_64 = stream.read(64)
    stream.seek(0)
    data = None
    o_cals = [0]
    if fitdecode and _is_fit_file(first_64):
            data = HRTrackerData()
            data.points = _decode_fit_file(stream, data)
    elif _is_pnn_sgt_file(first_64):
        data = HRTrackerData()
        data.points = _decode_pnn_sgt_file(stream, filename, data)

    if not data:
        raise CannotDecodeFileException()

    return data

#
# fit file handling
#
if fitdecode:
    # The default processor stringifies the timestamp so override
    # the timestamp handler to return the normalized timestamp
    class _UtcTimeProcessor(fitdecode.DefaultDataProcessor):
        def __init__(self):
            super().__init__()

        def process_type_date_time(self, reader, field_data):
                    if (field_data.value is not None
                    and field_data.value >= fitdecode.FIT_DATETIME_MIN):
                        field_data.value = fitdecode.FIT_UTC_REFERENCE \
                                           + field_data.value

    def _is_fit_file(data):
        return data[8:12] == b'.FIT'

    def _decode_fit_file(stream, container):
        try:
            with fitdecode.FitReader(stream, processor = _UtcTimeProcessor()) \
            as reader:
                for frame in reader:
                    if isinstance(frame, fitdecode.FitDataMessage):
                        if frame.name == 'record':
                            hr,ts =(None,None)
                            for field in frame.fields:
                                if field.name == 'timestamp':
                                    ts=field.value
                                elif field.name == 'heart_rate':
                                    hr=field.value
                            # There was a case of input with an incomplete
                            # record. Check that both are available before
                            # emitting
                            if ts and hr:
                                yield Datum(ts, hr)
                        elif frame.name == 'session':
                            container.cals = frame.get_value('total_calories')
        except fitdecode.exceptions.FitError:
            pass

#
# pnn-sgt file handling
#
def _is_pnn_sgt_file(data):
    # validate first line to check format sanity
    try:
        first_ln = str(data.partition(b'\n')[0], 'utf-8')
        time = int(first_ln.split(';')[0])
        datetime.fromtimestamp(time / 1000)
        return True
    except (UnicodeDecodeError, ValueError, OverflowError, OSError):
        return False

def _decode_pnn_sgt_file(stream, filename, container):
    for line in stream:
        try:
            xdata = str(line, 'utf-8')
        # handle non-text file
        except UnicodeDecodeError:
            xdata = ''
        data = xdata.split(';')
        if len(data) != 4 or data[2] != 'Heart rate':
            continue
        # normalize [0] from msec to sec
        yield Datum(int(data[0])/1000, int(data[3]))
    stream.close()
    if filename:
        m = re.search(r'#calories=([0-9]+)#', filename)
        if m:
            container.cals = m.group(1)
