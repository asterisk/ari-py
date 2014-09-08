#!/usr/bin/env python

"""WebSocket testing.
"""

import unittest
import ari
import httpretty

from ari_test.utils import AriTestCase
from swaggerpy.http_client import SynchronousHttpClient

BASE_URL = "http://ari.py/ari"

GET = httpretty.GET
PUT = httpretty.PUT
POST = httpretty.POST
DELETE = httpretty.DELETE


# noinspection PyDocstring
class WebSocketTest(AriTestCase):
    def setUp(self):
        super(WebSocketTest, self).setUp()
        self.actual = []

    def record_event(self, event):
        self.actual.append(event)

    def test_empty(self):
        uut = connect(BASE_URL, [])
        uut.on_event('ev', self.record_event)
        uut.run('test')
        self.assertEqual([], self.actual)

    def test_series(self):
        messages = [
            '{"type": "ev", "data": 1}',
            '{"type": "ev", "data": 2}',
            '{"type": "not_ev", "data": 3}',
            '{"type": "not_ev", "data": 5}',
            '{"type": "ev", "data": 9}'
        ]
        uut = connect(BASE_URL, messages)
        uut.on_event("ev", self.record_event)
        uut.run('test')
        expected = [
            {"type": "ev", "data": 1},
            {"type": "ev", "data": 2},
            {"type": "ev", "data": 9}
        ]
        self.assertEqual(expected, self.actual)

    def test_unsubscribe(self):
        messages = [
            '{"type": "ev", "data": 1}',
            '{"type": "ev", "data": 2}'
        ]
        uut = connect(BASE_URL, messages)
        self.once_ran = 0

        def only_once(event):
            self.once_ran += 1
            self.assertEqual(1, event['data'])
            self.once.close()

        def both_events(event):
            self.record_event(event)

        self.once = uut.on_event("ev", only_once)
        self.both = uut.on_event("ev", both_events)
        uut.run('test')

        expected = [
            {"type": "ev", "data": 1},
            {"type": "ev", "data": 2}
        ]
        self.assertEqual(expected, self.actual)
        self.assertEqual(1, self.once_ran)

    def test_on_channel(self):
        self.serve(DELETE, 'channels', 'test-channel')
        messages = [
            '{ "type": "StasisStart", "channel": { "id": "test-channel" } }'
        ]
        uut = connect(BASE_URL, messages)

        def cb(channel, event):
            self.record_event(event)
            channel.hangup()

        uut.on_channel_event('StasisStart', cb)
        uut.run('test')

        expected = [
            {"type": "StasisStart", "channel": {"id": "test-channel"}}
        ]
        self.assertEqual(expected, self.actual)

    def test_on_channel_unsubscribe(self):
        messages = [
            '{ "type": "StasisStart", "channel": { "id": "test-channel1" } }',
            '{ "type": "StasisStart", "channel": { "id": "test-channel2" } }'
        ]
        uut = connect(BASE_URL, messages)

        def only_once(channel, event):
            self.record_event(event)
            self.once.close()

        self.once = uut.on_channel_event('StasisStart', only_once)
        uut.run('test')

        expected = [
            {"type": "StasisStart", "channel": {"id": "test-channel1"}}
        ]
        self.assertEqual(expected, self.actual)

    def test_channel_on_event(self):
        self.serve(GET, 'channels', 'test-channel',
                   body='{"id": "test-channel"}')
        self.serve(DELETE, 'channels', 'test-channel')
        messages = [
            '{"type": "ChannelStateChange", "channel": {"id": "ignore-me"}}',
            '{"type": "ChannelStateChange", "channel": {"id": "test-channel"}}'
        ]

        uut = connect(BASE_URL, messages)
        channel = uut.channels.get(channelId='test-channel')

        def cb(channel, event):
            self.record_event(event)
            channel.hangup()

        channel.on_event('ChannelStateChange', cb)
        uut.run('test')

        expected = [
            {"type": "ChannelStateChange", "channel": {"id": "test-channel"}}
        ]
        self.assertEqual(expected, self.actual)

    def test_arbitrary_callback_arguments(self):
        self.serve(GET, 'channels', 'test-channel',
                   body='{"id": "test-channel"}')
        self.serve(DELETE, 'channels', 'test-channel')
        messages = [
            '{"type": "ChannelDtmfReceived", "channel": {"id": "test-channel"}}'
        ]
        obj = {'key': 'val'}

        uut = connect(BASE_URL, messages)
        channel = uut.channels.get(channelId='test-channel')

        def cb(channel, event, arg):
            if arg == 'done':
                channel.hangup()
            else:
                self.record_event(arg)

        def cb2(channel, event, arg1, arg2=None, arg3=None):
            self.record_event(arg1)
            self.record_event(arg2)
            self.record_event(arg3)

        channel.on_event('ChannelDtmfReceived', cb, 1)
        channel.on_event('ChannelDtmfReceived', cb, arg=2)
        channel.on_event('ChannelDtmfReceived', cb, obj)
        channel.on_event('ChannelDtmfReceived', cb2, 2.0, arg3=[1, 2, 3])
        channel.on_event('ChannelDtmfReceived', cb, 'done')
        uut.run('test')

        expected = [1, 2, obj, 2.0, None, [1, 2, 3]]
        self.assertEqual(expected, self.actual)

    def test_bad_event_type(self):
        uut = connect(BASE_URL, [])
        try:
            uut.on_object_event(
                'BadEventType', self.noop, self.noop, 'Channel')
            self.fail("Event does not exist")
        except ValueError:
            pass

    def test_bad_object_type(self):
        uut = connect(BASE_URL, [])
        try:
            uut.on_object_event('StasisStart', self.noop, self.noop, 'Bridge')
            self.fail("Event has no bridge")
        except ValueError:
            pass

    # noinspection PyUnusedLocal
    def noop(self, *args, **kwargs):
        self.fail("Noop unexpectedly called")


class WebSocketStubConnection(object):
    """Stub WebSocket connection.

    :param messages:
    """

    def __init__(self, messages):
        self.messages = list(messages)
        self.messages.reverse()

    def recv(self):
        """Fake receive method

        :return: Next message, or None if no more messages.
        """
        if self.messages:
            return str(self.messages.pop())
        return None

    def send_close(self):
        """Fake send_close method
        """
        return

    def close(self):
        """Fake close method
        """
        return


class WebSocketStubClient(SynchronousHttpClient):
    """Stub WebSocket client.

    :param messages: List of messages to return.
    :type  messages: list
    """

    def __init__(self, messages):
        super(WebSocketStubClient, self).__init__()
        self.messages = messages

    def ws_connect(self, url, params=None):
        """Fake connect method.

        Returns a WebSocketStubConnection, which itself returns the series of
        messages from WebSocketStubClient in its recv() method.

        :param url: Ignored.
        :param params: Ignored.
        :return: Stub connection.
        """
        return WebSocketStubConnection(self.messages)


def raise_exceptions(ex):
    """Testing exception handler for ARI client.

    :param ex: Exception caught by the event loop.
    """
    raise


def connect(base_url, messages):
    """Connect, with a WebSocket client test double that merely retuns the
     series of given messages.

    :param base_url: Base URL for REST calls.
    :param messages: Message strings to return from the WebSocket.
    :return: ARI client with stubbed WebSocket.
    """
    http_client = WebSocketStubClient(messages)
    client = ari.Client(base_url, http_client)
    client.exception_handler = raise_exceptions
    return client


if __name__ == '__main__':
    unittest.main()
