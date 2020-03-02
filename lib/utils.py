# hrtracker-suite
#
# Copyright (c) 2020 Andrey V
# All rights reserved.
#
# This code is licensed under the 3-clause BSD License.
# See the LICENSE file at the root of this project.

__all__ = ['deferred_value', 'try_get_value']

def deferred_value(name, val):
    """
    Safely get a value that may not exist.
    Raise LookupError on the name if the value doesn't exist.
    This is intended as a helper for getters.
    """
    if val:
        return val
    raise LookupError(f'{name} not ready')

def try_get_value(obj, name, default):
    """
    Try to get a value that may not exist.
    If `obj.name` doesn't have a value, `default` is returned.
    """
    try:
        return getattr(obj, name)
    except LookupError:
        return default
