# hrtracker-suite
#
# Copyright (c) 2020 Andrey V
# All rights reserved.
#
# This code is licensed under the 3-clause BSD License.
# See the LICENSE file at the root of this project.

from itertools import chain

from .types import HRTrackerIterable, HRTrackerData

__all__ = ['HRTrackerFilter', 'HRTrackerIdentityTransform',
           'HRTrackerMerger', 'HRTrackerSplitter']

"""
This module contains transformers. A transformer is a proxy for a
HRTrackerIterable that does some kind of filter operation.

Some transformations may be one-to-many or many-to-one.
"""

class HRTrackerFilter(HRTrackerIterable):
    """
    A filter container for heart rate tracker data.
    Common usage:


    `for data in HRTrackerFilter(decode_workout(...), hr_min=a, hr_max=b):`
        ...
    
    `data` will contain heart rate points with values between `a` and `b`
    """

    def __init__(self, tracker, hr_min = 0, hr_max = 220):
        super().__init__()
        self._tracker = tracker
        self._hr_min = hr_min
        self._hr_max = hr_max

    def __iter__(self):
        for datum in self._tracker:
            if datum[1] >= self._hr_min and datum[1] <= self._hr_max:
                yield datum

    @property
    def hr_min(self):
        """Read-only access to the minimum heart rate."""
        return self._hr_min

    @property
    def hr_max(self):
        """Read-only access to the maximum heart rate."""
        return self._hr_max

    # proxy other attributes to the tracker
    def __getattr__(self, name):
        return getattr(self._tracker, name)

    def __setattr__(self, name, value):
        # the attributes to proxy
        if name in ['points', 'cals']:
            self._tracker.__setattr__(name, value)
        else:
            super.__setattr__(self, name, value)

class HRTrackerIdentityTransform(HRTrackerIterable):
    """
    An identity container for heart rate tracker data.
    This is useful for something like:

    if thing:
        Filter = HRTrackerFilter
    else:
        Filter = HRTrackerIdentityTransform
    """

    def __init__(self, tracker, *args, **kwargs):
        super().__init__()
        super.__setattr__(self, '_tracker', tracker)

    def __iter__(self):
        for datum in self._tracker:
            yield datum

    # proxy other attributes to the tracker
    def __getattr__(self, name):
        return getattr(self._tracker, name)

    def __setattr__(self, name, value):
        # the attributes to proxy
        if name in ['points', 'cals']:
            self._tracker.__setattr__(name, value)
        else:
            raise AttributeError()

def HRTrackerMerger(*trackers, **kwargs):
    """
    A merging container for heart rate tracker data.
    This is a many-to-one transformation.
    """
    return \
        HRTrackerIdentityTransform(HRTrackerData(
            chain(*trackers)
        ))

class HRTrackerSplitter(HRTrackerIterable):
    """
    A splitter container for heart rate tracker data.
    This is a one-to-many transformation.

    Common usage:


    `for data in HRTrackerSplitter(decode_workout(...), split_at = t):`
        ...
    
    `data` will contain buffer that is a HRTrackerData
    """
    
    def __init__(self, tracker, split_at = 60*60):
        super().__init__()
        self._tracker = tracker
        self._split_at = split_at

    def __iter__(self):
        # Split by self._split_at
        # Ignore calorie estimate because infeasible with generator model
        buf = []
        start_t = None
        split_t = self._split_at
        for datum in self._tracker:
            if not start_t:
                start_t = datum[0]
            if datum[0] >= start_t + split_t:
                yield HRTrackerData(buf, 1)
                start_t = datum[0]
                buf = []
            buf.append(datum)

        yield HRTrackerData(buf, 1)
    
    @property
    def split_time(self):
        """Read-only access to the time per split"""
        return self._split_at

    # proxy other attributes to the tracker
    def __getattr__(self, name):
        return getattr(self._tracker, name)

    def __setattr__(self, name, value):
        # the attributes to proxy
        # Only `.points` is proxied because we only care about the generator
        if name in ['points']:
            self._tracker.__setattr__(name, value)
        else:
            super.__setattr__(self, name, value)

