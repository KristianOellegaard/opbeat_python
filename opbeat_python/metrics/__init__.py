"""
opbeat_python.metrics
~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

:license: BSD, see LICENSE for more details.
"""


import threading
from timeit import default_timer

from collections import defaultdict
from datetime import datetime
from contextlib import contextmanager

from opbeat_python.metrics.aggregator import Aggregator
from opbeat_python.conf.defaults import METRIC_FLUSH_TIME_LIMIT

lock = threading.RLock()

aggregator = Aggregator()

threadlocal = threading.local()
threadlocal.timings = {}


__last_flush = datetime.now()
__client = None

__all__ = ('set_client', 'get_client', 'begin_measure', 'end_measure',
           'record_value', 'record_value', 'flush_metrics')


def set_client(new_client):
    global __client
    __client = new_client


def get_client():
    global __client
    return __client


def begin_measure(metric, segments={}):
    key = (metric, frozenset(segments.items()))
    threadlocal.timings[key] = default_timer()


def end_measure(metric, segments={}):
    key = (metric, frozenset(segments.items()))
    if key in threadlocal.timings:
        elapsed_time = default_timer() - threadlocal.timings[key]
        del threadlocal.timings[key]
        record_value(metric, elapsed_time, segments)


@contextmanager
def measure(metric, segments={}):
    begin_measure(metric, segments)
    yield
    end_measure(metric, segments)


def record_value(metric, value, segments={}):
    global __last_flush

    try:
        lock.acquire()
        aggregator.record_point(metric, value, segments)

        td = (datetime.now() - __last_flush)
        seconds_since_last_flush = (td.seconds + td.days * 24 * 3600)

        if seconds_since_last_flush >= METRIC_FLUSH_TIME_LIMIT:
            flush_metrics()
    finally:
        lock.release()

filtered_values = ['metric', 'timestamp']


def flush_metrics():
    global __last_flush
    global __client

    try:
        lock.acquire()
        __last_flush = datetime.now()
        values = aggregator.get_and_clear_values()
    finally:
        lock.release()

    metrics = defaultdict(lambda: defaultdict(list))

    for point in values:
        metrics[point['metric']][point['timestamp']].append(point)

    new_values = []
    for metric, point in metrics.items():
        value = {'metric': metric, 'points': []}
        for timestamp, values in point.items():
            v = [
                    dict((k, v) for (k, v) in val.items() if k not in filtered_values)
                    for val in values
                ]
            value['points'].append(
                {
                    'time': timestamp,
                    'values': v
                }
            )
        new_values.append(value)

    __client.send(new_values)
