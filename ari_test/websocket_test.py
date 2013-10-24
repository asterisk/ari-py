#!/usr/bin/env python

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


class WebSocketTest(AriTestCase):
    def setUp(self):
        super(WebSocketTest, self).setUp()
        self.actual = []

    def record_event(self, event):
        self.actual.append(event)

    def test_empty(self):
        uut = connect(BASE_URL, 'test', [])
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
        uut = connect(BASE_URL, 'test', messages)
        uut.on_event("ev", self.record_event)
        uut.run('test')
        expected = [
            {"type": "ev", "data": 1},
            {"type": "ev", "data": 2},
            {"type": "ev", "data": 9}
        ]
        self.assertEqual(expected, self.actual)

    def test_on_channel(self):
        self.serve(DELETE, 'channel', 'test-channel')
        messages = [
            '{ "type": "StasisStart", "channel": { "id": "test-channel" } }'
        ]
        uut = connect(BASE_URL, 'test', messages)

        def cb(channel, event):
            self.record_event(event)
            channel.hangup()

        uut.on_channel_event('StasisStart', cb)
        uut.run('test')

        expected = [
            {"type": "StasisStart", "channel": {"id": "test-channel"}}
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

        uut = connect(BASE_URL, 'test', messages)
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

    def test_bad_event_type(self):
        uut = connect(BASE_URL, 'test', [])
        try:
            uut.on_object_event(
                'BadEventType', self.noop, self.noop, 'Channel')
            self.fail("Event does not exist")
        except ValueError:
            pass

    def test_bad_object_type(self):
        uut = connect(BASE_URL, 'test', [])
        try:
            uut.on_object_event('StasisStart', self.noop, self.noop, 'Bridge')
            self.fail("Event has no bridge")
        except ValueError:
            pass

    def noop(self, *args, **kwargs):
        self.fail("Noop unexpectedly called")


class WebSocketStubConnection(object):
    def __init__(self, messages):
        self.messages = list(messages)
        self.messages.reverse()

    def recv(self):
        if self.messages:
            return str(self.messages.pop())
        return None


class WebSocketStubClient(SynchronousHttpClient):
    """Stub WebSocket connection.

    :param messages: List of messages to return.
    :type  messages: list
    """

    def __init__(self, messages):
        super(WebSocketStubClient, self).__init__()
        self.messages = messages

    def ws_connect(self, url, params=None):
        return WebSocketStubConnection(self.messages)


def connect(base_url, apps, messages):
    http_client = WebSocketStubClient(messages)
    return ari.Client(base_url, http_client)


if __name__ == '__main__':
    unittest.main()
