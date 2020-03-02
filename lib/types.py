# hrtracker-suite
#
# Copyright (c) 2020 Andrey V
# All rights reserved.
#
# This code is licensed under the 3-clause BSD License.
# See the LICENSE file at the root of this project.

from collections import namedtuple
from .utils import deferred_value

__all__ = ['Datum', 'HRTrackerIterable', 'HRTrackerData']

Datum = namedtuple('Datum', ['ts', 'hr'])
"""
A `Datum` is a tuple type that describes a pair of timestamp and heart rate.
"""

class HRTrackerIterable:
    """
    Abstract base class for heart rate tracker iterables.
    This allows for use of, among other things, filters.
    """
    __slots__ = ()

    def __init__(self):
        pass

    def __iter__(self):
        pass

class HRTrackerData(HRTrackerIterable):
    """
    A container for heart rate tracker data.

    Create a container and use setters to load the:
    (1) points generator
    (2) start time
    (3) end time
    (4) cals

    The object can be iterated over to yield the points.
    `end_time` is to be set by the consumer
    """
    def __init__(self, iterable = None, cals = None):
        super().__init__()
        self._points = iterable
        self._cals = cals
        self._reset_times()

    def __iter__(self):
        if self._points:
            start, end = None, None
            for point in self._points:
                if not start:
                    start = point[0]
                yield point
                end = point[0]
            self._start = start
            self._end = end
            self._reset_generator()
        else:
            return deferred_value('points', None)

    # points is write-only as read is designed to only be used via generator
    def points(self, generator):
        self._points = generator
        self._reset_times()

    points = property(None, points)

    @property
    def start_time(self):
        """
        Attempt to get the start time.
        Raise LookupError if unavailable.
        """
        return deferred_value('start_time', self._start)

    @property
    def end_time(self):
        """
        Attempt to get the end time.
        Raise LookupError if unavailable.
        """
        return deferred_value('end_time', self._end)

    @property
    def cals(self):
        """
        Attempt to get the calorie estimate.
        Raise LookupError if unavailable.
        """
        return deferred_value('cals', self._cals)
    
    @cals.setter
    def cals(self, val):
        """
        Set the calorie estimate value.
        Raise LookupError if unavailable.
        """
        self._cals = val

    # Reset generator after exhaustion.
    def _reset_generator(self):
        self._points = None

    # These values are calculated from the tracker data. Mark unavailable
    # on reset.
    def _reset_times(self):
        self._start = None
        self._end = None

