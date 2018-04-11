#!/usr/bin/env python

import paho.mqtt.client as mqtt
import time
import threading
import urwid

#########################################################
# Display stuff
#########################################################

class MqttData(object):
    def __init__(self, params):
        self.topic = params['topic']
        self.name = params['name']
        self.timeout = float(params['timeout'])

        self.last_time = 0.0
        self.value = None

    def update(self, value):
        self.value = value
        self.last_time = time.time()

    def draw(self):
        dt = time.time() - self.last_time

        if (dt < self.timeout):
            color = 'good'
        else:
            color = 'stale'

        cols = urwid.Columns([])
        cols.contents.append((urwid.AttrMap(urwid.Text(self.name), color), cols.options()))
        cols.contents.append((urwid.AttrMap(urwid.Text(str(self.value)), color), cols.options()))
        return cols

class MqttWidget(urwid.Pile):
    ''' Class used to draw the data from the Printer. '''
    def __init__(self, params):
        urwid.Pile.__init__(self, [])

        self.connected = False

        self.params = params
        self.host = params['host']
        self.data = []
        for machine in params['machines']:
            for data in machine['messages']:
                self.data.append(MqttData(data))
        self.client = mqtt.Client()

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.stats_lock = threading.Lock()

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe('#')
        self.connected = True

    def on_disconnect(self, client, userdata, rc):
        self.connected = False

    def on_message(self, client, userdata, msg):
        self.stats_lock.acquire(True)
        for item in self.data:
            if msg.topic == item.topic:
                item.update(msg.payload)
        self.stats_lock.release()

    def getPalette(self):
        ''' Used to populate the pallete. '''
        return [
            ('good', 'light blue', '', '', 'light blue', ''),
            ('stale', 'light red', '', '', 'light red', ''),
        ]

    def update(self, loop, data):
        rows = []

        connected = "Disconnected"
        if connected:
            connected = "Connected"
        rows.append((urwid.AttrMap(urwid.Text('Mqtt(%s): %s' % (self.host, connected)), 'title'), self.options()))

        self.stats_lock.acquire(True)
        for row in self.data:
            rows.append((row.draw(), self.options()))
        self.stats_lock.release()

        self.contents = rows
        loop.set_alarm_in(1.0, self.update)

    def start(self, loop):
        ''' Called to add the initial processes to the loop.'''
        self.client.connect_async(self.params['host'], port=self.params['port'])
        self.client.loop_start()
        self.update(loop, None)

    def getError(self):
        ''' return if there is a problem that I can detect. '''
        return None


