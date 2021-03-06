"""
opbeat.handlers.logbook
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logbook
import sys
import traceback

from opbeat.base import Client
from opbeat.utils.encoding import to_string

LOOKBOOK_LEVELS = {
    logbook.DEBUG:'debug',
    logbook.INFO: 'info',
    logbook.NOTICE: 'info',
    logbook.WARNING: 'warning',
    logbook.ERROR: 'error',
    logbook.CRITICAL:'fatal',
}


class OpbeatHandler(logbook.Handler):
    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            arg = args[0]
            # if isinstance(arg, basestring):
            #     self.client = kwargs.pop('client_cls', Client)(dsn=arg)
            if isinstance(arg, Client):
                self.client = arg
            else:
                raise ValueError('The first argument to %s must be a Client instance got %r instead.' % (
                    self.__class__.__name__,
                    arg,
                ))
            args = []
        else:
            try:
                self.client = kwargs.pop('client')
            except KeyError:
                raise TypeError('Expected keyword argument for OpbeatHandler: client')
        super(OpbeatHandler, self).__init__(*args, **kwargs)

    def emit(self, record):
        # from sentry.client.middleware import OpbeatLogMiddleware

        # # Fetch the request from a threadlocal variable, if available
        # request = getattr(OpbeatLogMiddleware.thread, 'request', None)
        self.format(record)

        # Avoid typical config issues by overriding loggers behavior
        if record.channel.startswith('opbeat.errors'):
            print >> sys.stderr, to_string(record.message)
            return

        try:
            return self._emit(record)
        except Exception:
            print >> sys.stderr, "Top level Opbeat exception caught - failed creating log record"
            print >> sys.stderr, to_string(record.msg)
            print >> sys.stderr, to_string(traceback.format_exc())

            try:
                self.client.capture('Exception')
            except Exception:
                pass

    def _emit(self, record):
        data = {
            'level': LOOKBOOK_LEVELS[record.level],
            'logger': record.channel,
        }

        # If there's no exception being processed, exc_info may be a 3-tuple of None
        # http://docs.python.org/library/sys.html#sys.exc_info
        if record.exc_info is True or (record.exc_info and all(record.exc_info)):
            handler = self.client.get_handler('opbeat.events.Exception')

            data.update(handler.capture(exc_info=record.exc_info))
        
        return self.client.capture('Message',
            param_message=
                {
                    'message':record.msg,
                    'params':record.args
                },
            data=data,
            extra=record.extra,
        )
