#!/usr/bin/env python

"""Brief example of using the channel API.

This app will answer any channel sent to Stasis(hello), and play "Hello,
world" to the channel. For any DTMF events received, the number is played back
to the channel. Press # to hang up, and * for a special message.
"""

#
# Copyright (c) 2013, Digium, Inc.
#

import ari

client = ari.connect('http://localhost:8088/', 'hey', 'peekaboo')


def on_dtmf(channel, event):
    """Callback for DTMF events.

    When DTMF is received, play the digit back to the channel. # hangs up,
    * plays a special message.

    :param channel: Channel DTMF was received from.
    :param event: Event.
    """
    digit = event['digit']
    if digit == '#':
        channel.play(media='sound:goodbye')
        channel.continueInDialplan()
    elif digit == '*':
        channel.play(media='sound:asterisk-friend')
    else:
        channel.play(media='sound:digits/%s' % digit)


def on_start(channel, event):
    """Callback for StasisStart events.

    On new channels, register the on_dtmf callback, answer the channel and
    play "Hello, world"

    :param channel: Channel DTMF was received from.
    :param event: Event.
    """
    channel.on_event('ChannelDtmfReceived', on_dtmf)
    channel.answer()
    channel.play(media='sound:hello-world')


client.on_channel_event('StasisStart', on_start)

# Run the WebSocket
client.run(apps="hello")
