# hrtracker-suite
#
# Copyright (c) 2020 Andrey V
# All rights reserved.
#
# This code is licensed under the 3-clause BSD License.
# See the LICENSE file at the root of this project.

from collections import namedtuple
from .types import HRTrackerIterable
from .utils import deferred_value, try_get_value

__all__ = ['HeartPointConfig', 'PnnSgtLogfile']

"""
This module contains HRTrackerIterable consumers. A consumer consumes
the pipeline and yields a different kind of object, which contain their own
start times and some kind of data, be it a value or a generator.
"""

class HeartPointConfig:
    """
    Configure a heart point calculator instance.
    
    Heart points are determined by time above a certain heart rate relative to
    maximum heart rate. This Config creates an instance that allows for 
    heart point calculation given any of
    - maximum heart rate (`hr_max`),
    - minimum percentage of the first for moderate exercise,
    - minimum percentage of the first for vigorous exercise, or
    - minimum percentage of the first for extra-vigorous exercise.

    Given a Config, the heart points for a workout can be calculated by calling
    the heart_points method with a given workout.
    """

    def __init__(self, *, hr_max = 220,
                 pct_mod = 0.6, pct_hi = 0.7, pct_xhi = 0.85):

        # Range checks
        def _check_pct(val, name):
            try:
                if not (val > 0.0 and val < 1.0):
                    raise ValueError(f'{name} is not a float within (0,1)')
            except TypeError:
                raise TypeError(f'{name} is not a float')

        try:
            if not (hr_max > 0 and hr_max <= 220):
                raise ValueError('hr_max is not an int within (0, 220]')
        except TypeError:
            raise TypeError('hr_max is not an int')

        _pcts = [[pct_mod, 'pct_mod'],
                 [pct_hi, 'pct_hi'],
                 [pct_xhi, 'pct_xhi']]
        for p in _pcts:
            _check_pct(p[0], p[1])


        self._cutoffs = HeartPointConfig.get_cutoffs(
               **{ 'hr_max': hr_max,
                 'pct_mod': pct_mod, 'pct_hi': pct_hi, 'pct_xhi': pct_xhi })
        self._last_off = len(self._cutoffs) - 1

    HeartPointObject = namedtuple('HeartPointObject',
                                  ['start', 'end', 'points', 'cals'])
    
    @staticmethod
    def get_cutoffs(**kw):
        """
        Generate cutoff vectors given kw args hr_max, pct_mod, pct_hi, pct_xhi
        """
        return [int(kw['hr_max']) * float(kw['pct_' + pct]) \
                for pct in ('mod', 'hi', 'xhi')]
    

    def heart_points(self, workout):
        """
        Get the number of heart points for `workout`.

        Args:
        workout: an `HRTrackerIterable` (usually a `HRTrackerData`
                                         or `HRTrackerFilter` instance)
        """
        if not isinstance(workout, HRTrackerIterable):
            raise TypeError(f'expected HRTrackerIterable; got {type(workout)}')

        def _points_for_pair(x0, x1):
            # Each point produced by a HRTrackerIterable is a pair of
            # [Posix timestamp, HR]
            nmins = (x1[0] - x0[0]) / 60
            avg_hr = (x1[1] + x0[1]) / 2
            for cat in range(self._last_off, -1, -1):
                if avg_hr >= self._cutoffs[cat]:
                    return nmins * (cat + 1)
            return 0.0

        npoints = 0.0
        oldval = None

        # This pair of functions is used to get overlapping pairs from the
        # generator in `workout`
        def _firstval(w):
            nonlocal oldval
            oldval = w

        def _nextval(w):
            nonlocal npoints, oldval
            npoints += _points_for_pair(oldval, w)
            oldval = w
        
        _vfunc = _firstval
        for w in workout:
            _vfunc(w)
            _vfunc = _nextval

        # workout is consumed by now; it should be safe to access start_time
        # and end_time without LookupError
        
        return HeartPointConfig.HeartPointObject(
                   workout.start_time, workout.end_time,
                   round(npoints), try_get_value(workout, 'cals', 0))

class PnnSgtLogfile:
    """
    Encoder for PNN-SGT log file.
    
    Invoke with a generator for a tracker that will act as the data source.
    """
    # NOTE: This is a consumer not a transformer because the output iterable
    # is a log file line generator not a HRTrackerData
    def __init__(self, tracker):
        self._tracker = tracker
        self._start = None
        self._elapsed = None
        self._cals = None
        self._filename = None

    def __iter__(self):
        if self._tracker:
            has_pt = False
            for point in self._tracker:
                has_pt = True
                yield f'{point[0]}000;;Heart rate;{point[1]}\n'\
                      .encode('utf-8')
            if has_pt:
                self._start = self._tracker.start_time
                self._elapsed = self._tracker.end_time - self._start
                self._cals = int(self._tracker.cals)
                self._filename = f'#date={self._start}000#' + \
                                 f'time={self._elapsed}000#' + \
                                 f'calories={self._cals}#' + \
                                 'type=HeartRate#spmax=0#version=4.txt'
        else:
            return deferred_value('tracker', None)

    # tracker is write-only as read is designed to only be used via generator
    def tracker(self, generator):
        self._tracker = generator
        self._reset_vals()

    tracker = property(None, tracker)

    @property
    def start_time(self):
        """
        Attempt to get the start time.
        Raise LookupError if unavailable.
        """
        return deferred_value('start_time', self._start)

    @property
    def elapsed_time(self):
        """
        Attempt to get the elapsed time.
        Raise LookupError if unavailable.
        """
        return deferred_value('elapsed_time', self._elapsed)

    @property
    def cals(self):
        """
        Attempt to get the calorie estimate.
        Raise LookupError if unavailable.
        """
        return deferred_value('cals', self._cals)

    @property
    def filename(self):
        """
        Attempt to get the file name.
        Raise LookupError if unavailable.
        """
        return deferred_value('filename', self._filename)

    def _reset_vals(self):
        # These values are calculated from the tracker data. Mark unavailable
        # on reset.
        self._start = None
        self._elapsed = None
        self._filename = None

