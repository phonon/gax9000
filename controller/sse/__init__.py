"""
Flask Server Side Event (SSE) channel implementation:
https://github.com/singingwolfboy/flask-sse/issues/7
"""
from typing import Iterator
import random
import string
import json
import logging

from collections import deque
from flask import Response, request
from gevent.queue import Queue
import gevent


def generate_id(size=6, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class ServerSentEvent(object):
    """Class to handle server-sent events."""
    def __init__(self, data, event):
        self.data = data
        self.event = event
        self.event_id = generate_id()
        self.desc_map = {
            self.data: "data",
            self.event: "event",
            self.event_id: "id"
        }

    def encode(self) -> str:
        """Encodes events as a string."""
        if not self.data:
            return ""
        lines = ["{}: {}".format(name, key)
                 for key, name in self.desc_map.items() if key]

        return "{}\n\n".format("\n".join(lines))


class EventChannel(object):
    def __init__(self, history_size=32):
        self.subscriptions = []
        self.history = deque(maxlen=history_size)
        self.history.append(ServerSentEvent('start_of_history', None))

    def notify(self, message):
        """Notify all subscribers with message.
        Apparently issue occuring with SSE clients not signaling closed 
        properly...so this raises an error when flask backend publishes to
        a closed SSE...
        """
        for sub in self.subscriptions[:]:
            sub.put(message)

    def event_generator(self, last_id) -> Iterator[ServerSentEvent]:
        """Yields encoded ServerSentEvents."""
        q = Queue()
        self._add_history(q, last_id)
        self.subscriptions.append(q)
        try:
            while True:
                yield q.get()
                gevent.sleep(0.1) # required to prevent blocking thread
        finally: # should occur after `GeneratorExit` exception
            self.subscriptions.remove(q)

    def subscribe(self):
        def gen(last_id) -> Iterator[str]:
            for sse in self.event_generator(last_id):
                yield sse.encode()
        res = Response(
            gen(request.headers.get("Last-Event-ID")),
            mimetype="text/event-stream",
        )
        res.headers["Content-Type"] = "text/event-stream;charset=utf-8"
        res.headers["Cache-Control"] = "no-cache, no-transform"
        res.headers["Connection"] = "keep-alive"

        return res
    
    def _add_history(self, q, last_id):
        add = False
        for sse in self.history:
            if add:
                q.put(sse)
            if sse.event_id == last_id:
                add = True

    def publish(self, message):
        # IMPORTANT!: use json.dumps
        # just making a str(message) may use single quotes which
        # cannot be parsed as proper json by client listener
        sse = ServerSentEvent(json.dumps(message), None)
        self.history.append(sse)
        gevent.spawn(self.notify, sse)

    def get_last_id(self) -> str:
        return self.history[-1].event_id