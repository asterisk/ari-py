#
# Copyright (c) 2013, Digium, Inc.
#

"""ARI client library.
"""

import json
import logging
import urlparse
import swaggerpy.client

from ari.model import *

log = logging.getLogger(__name__)


class Client(object):
    """ARI Client object.

    :param base_url: Base URL for accessing Asterisk.
    :param http_client: HTTP client interface.
    """

    def __init__(self, base_url, http_client):
        url = urlparse.urljoin(base_url, "ari/api-docs/resources.json")

        self.swagger = swaggerpy.client.SwaggerClient(
            url, http_client=http_client)
        self.repositories = {
            name: Repository(self, name, api)
            for (name, api) in self.swagger.resources.items()}

        # Extract models out of the events resource
        events = [api['api_declaration']
                  for api in self.swagger.api_docs['apis']
                  if api['name'] == 'events']
        if events:
            self.event_models = events[0]['models']
        else:
            self.event_models = {}

        self.websockets = set()
        self.event_listeners = {}
        self.exception_handler = \
            lambda ex: log.exception("Event listener threw exception")

    def __getattr__(self, item):
        """Exposes repositories as fields of the client.

        :param item: Field name
        """
        repo = self.get_repo(item)
        if not repo:
            raise AttributeError(
                "'%r' object has no attribute '%s'" % (self, item))
        return repo

    def close(self):
        """Close this ARI client.

        This method will close any currently open WebSockets, and close the
        underlying Swaggerclient.
        """
        for ws in self.websockets:
            ws.send_close()
        self.swagger.close()

    def get_repo(self, name):
        """Get a specific repo by name.

        :param name: Name of the repo to get
        :return: Repository, or None if not found.
        :rtype:  ari.model.Repository
        """
        return self.repositories.get(name)

    def __run(self, ws):
        """Drains all messages from a WebSocket, sending them to the client's
        listeners.

        :param ws: WebSocket to drain.
        """
        # TypeChecker false positive on iter(callable, sentinel) -> iterator
        # Fixed in plugin v3.0.1
        # noinspection PyTypeChecker
        for msg_str in iter(lambda: ws.recv(), None):
            msg_json = json.loads(msg_str)
            if not isinstance(msg_json, dict) or 'type' not in msg_json:
                log.error("Invalid event: %s" % msg_str)
                continue

            listeners = list(self.event_listeners.get(msg_json['type'], []))
            for listener in listeners:
                # noinspection PyBroadException
                try:
                    listener(msg_json)
                except Exception as e:
                    self.exception_handler(e)

    def run(self, apps):
        """Connect to the WebSocket and begin processing messages.

        This method will block until all messages have been received from the
        WebSocket, or until this client has been closed.

        :param apps: Application (or list of applications) to connect for
        :type  apps: str or list of str
        """
        if isinstance(apps, list):
            apps = ','.join(apps)
        ws = self.swagger.events.eventWebsocket(app=apps)
        self.websockets.add(ws)
        try:
            self.__run(ws)
        finally:
            ws.close()
            self.websockets.remove(ws)

    def on_event(self, event_type, event_cb):
        """Register callback for events with given type.

        :param event_type: String name of the event to register for.
        :param event_cb: Callback function
        :type  event_cb: (dict) -> None
        """
        listeners = self.event_listeners.setdefault(event_type, set())
        listeners.add(event_cb)
        client = self

        class EventUnsubscriber(object):
            """Class to allow events to be unsubscribed.
            """

            def close(self):
                """Unsubscribe the associated event callback.
                """
                client.event_listeners[event_type].discard(event_cb)

        return EventUnsubscriber()

    def on_object_event(self, event_type, event_cb, factory_fn, model_id):
        """Register callback for events with the given type. Event fields of
        the given model_id type are passed along to event_cb.

        If multiple fields of the event have the type model_id, a dict is
        passed mapping the field name to the model object.

        :param event_type: String name of the event to register for.
        :param event_cb: Callback function
        :type  event_cb: (Obj, dict) -> None or (dict[str, Obj], dict) ->
        :param factory_fn: Function for creating Obj from JSON
        :param model_id: String id for Obj from Swagger models.
        """
        # Find the associated model from the Swagger declaration
        event_model = self.event_models.get(event_type)
        if not event_model:
            raise ValueError("Cannot find event model '%s'" % event_type)

        # Extract the fields that are of the expected type
        obj_fields = [k for (k, v) in event_model['properties'].items()
                      if v['type'] == model_id]
        if not obj_fields:
            raise ValueError("Event model '%s' has no fields of type %s"
                             % (event_type, model_id))

        def extract_objects(event):
            """Extract objects of a given type from an event.

            :param event: Event
            """
            # Extract the fields which are of the expected type
            obj = {obj_field: factory_fn(self, event[obj_field])
                   for obj_field in obj_fields
                   if event.get(obj_field)}
            # If there's only one field in the schema, just pass that along
            if len(obj_fields) == 1:
                if obj:
                    obj = obj.values()[0]
                else:
                    obj = None
            event_cb(obj, event)

        return self.on_event(event_type, extract_objects)

    def on_channel_event(self, event_type, fn):
        """Register callback for Channel related events

        :param event_type: String name of the event to register for.
        :param fn: Callback function
        :type  fn: (Channel, dict) -> None or (list[Channel], dict) -> None
        """
        return self.on_object_event(event_type, fn, Channel, 'Channel')

    def on_bridge_event(self, event_type, fn):
        """Register callback for Bridge related events

        :param event_type: String name of the event to register for.
        :param fn: Callback function
        :type  fn: (Bridge, dict) -> None or (list[Bridge], dict) -> None
        """
        return self.on_object_event(event_type, fn, Bridge, 'Bridge')

    def on_playback_event(self, event_type, fn):
        """Register callback for Playback related events

        :param event_type: String name of the event to register for.
        :param fn: Callback function
        :type  fn: (Playback, dict) -> None or (list[Playback], dict) -> None
        """
        return self.on_object_event(event_type, fn, Playback, 'Playback')

    def on_live_recording_event(self, event_type, fn):
        """Register callback for LiveRecording related events

        :param event_type: String name of the event to register for.
        :param fn: Callback function
        :type  fn: (LiveRecording, dict) -> None or (list[LiveRecording], dict) -> None
        """
        return self.on_object_event(event_type, fn, LiveRecording, 'LiveRecording')

    def on_stored_recording_event(self, event_type, fn):
        """Register callback for StoredRecording related events

        :param event_type: String name of the event to register for.
        :param fn: Callback function
        :type  fn: (StoredRecording, dict) -> None or (list[StoredRecording], dict) -> None
        """
        return self.on_object_event(event_type, fn, StoredRecording, 'StoredRecording')

    def on_endpoint_event(self, event_type, fn):
        """Register callback for Endpoint related events

        :param event_type: String name of the event to register for.
        :param fn: Callback function
        :type  fn: (Endpoint, dict) -> None or (list[Endpoint], dict) -> None
        """
        return self.on_object_event(event_type, fn, Endpoint, 'Endpoint')

    def on_device_state_event(self, event_type, fn):
        """Register callback for DeviceState related events

        :param event_type: String name of the event to register for.
        :param fn: Callback function
        :type  fn: (DeviceState, dict) -> None or (list[DeviceState], dict) -> None
        """
        return self.on_object_event(event_type, fn, DeviceState, 'DeviceState')

    def on_sound_event(self, event_type, fn):
        """Register callback for Sound related events

        :param event_type: String name of the event to register for.
        :param fn: Sound function
        :type  fn: (Sound, dict) -> None or (list[Sound], dict) -> None
        """
        return self.on_object_event(event_type, fn, Sound, 'Sound')
