#!/usr/bin/env python

"""Short example of how to use bridge objects.

This example will create a holding bridge (if one doesn't already exist). Any
channels that enter Stasis is placed into the bridge. Whenever a channel
enters the bridge, a tone is played to the bridge.
"""

#
# Copyright (c) 2013, Digium, Inc.
#

import ari

client = ari.connect('http://localhost:8088/', 'hey', 'peekaboo')

#
# Find (or create) a holding bridge.
#
bridges = [b for b in client.bridges.list() if
           b.json['bridge_type'] == 'holding']
if bridges:
    bridge = bridges[0]
    print "Using bridge %s" % bridge.id
else:
    bridge = client.bridges.create(type='holding')
    print "Created bridge %s" % bridge.id


def on_enter(bridge, ev):
    """Callback for bridge enter events.

    When channels enter the bridge, play tones to the whole bridge.

    :param bridge: Bridge entering the channel.
    :param ev: Event.
    """
    # ignore announcer channels - see ASTERISK-22744
    if ev['channel']['name'].startswith('Announcer/'):
        return
    bridge.play(media="sound:ascending-2tone")


bridge.on_event('ChannelEnteredBridge', on_enter)


def stasis_start_cb(channel, ev):
    """Callback for StasisStart events.

    For new channels, answer and put them in the holding bridge.

    :param channel: Channel that entered Stasis
    :param ev: Event
    """
    channel.answer()
    bridge.addChannel(channel=channel.id)


client.on_channel_event('StasisStart', stasis_start_cb)

# Run the WebSocket
client.run(apps='hello')
