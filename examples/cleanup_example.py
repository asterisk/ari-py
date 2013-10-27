#!/usr/bin/env python

"""ARI resources may be closed, if an application only needs them temporarily.
"""

#
# Copyright (c) 2013, Digium, Inc.
#

import ari
import logging
import sys
import thread

logging.basicConfig()

client = ari.connect('http://localhost:8088/', 'hey', 'peekaboo')


# noinspection PyUnusedLocal
def on_start(channel, event):
    """Callback for StasisStart events.

    On new channels, register the on_dtmf callback, answer the channel and
    play "Hello, world"

    :param channel: Channel DTMF was received from.
    :param event: Event.
    """
    on_dtmf_handle = None

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
            on_dtmf_handle.close()
        elif digit == '*':
            channel.play(media='sound:asterisk-friend')
        else:
            channel.play(media='sound:digits/%s' % digit)

    on_dtmf_handle = channel.on_event('ChannelDtmfReceived', on_dtmf)
    channel.answer()
    channel.play(media='sound:hello-world')


client.on_channel_event('StasisStart', on_start)

# Run the WebSocket
sync = thread.allocate_lock()


def run():
    """Thread for running the Websocket.
    """
    sync.acquire()
    client.run(apps="hello")
    sync.release()


thr = thread.start_new_thread(run, ())
print "Press enter to exit"
sys.stdin.readline()
client.close()
sync.acquire()
print "Application finished"
