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

        self.last_time = time.time()
        self.value = None

    def update(self, value):
        self.value = value
        self.last_time = time.time()

    def ok(self):
        dt = time.time() - self.last_time

        if (dt < self.timeout):
            return True
        return False

    def draw(self):
        if self.ok():
            color = 'good'
        else:
            color = 'stale'

        cols = urwid.Columns([])
        cols.contents.append((urwid.AttrMap(urwid.Text(self.name), color), cols.options()))
        cols.contents.append((urwid.AttrMap(urwid.Text(self.value_text()), color), cols.options()))
        return cols

    def value_text(self):
        return str(self.value)

class MqttTimedData(MqttData):
    ''' Also print how long the value has been at that value '''
    def __init__(self, params):
        MqttData.__init__(self, params)
        self.changed_time = time.time()

    def update(self, value):
        if self.value != value:
            self.changed_time = time.time()
        MqttData.update(self, value)

    def value_text(self):
        if self.value is None:
            return MqttData.value_text(self)

        changed_ago = time.time() - self.changed_time

        SECONDS_PER_MINUTE = 60.0
        SECONDS_PER_HOUR = 60.0 * SECONDS_PER_MINUTE
        SECONDS_PER_DAY = 24.0 * SECONDS_PER_HOUR
        SECONDS_PER_YEAR = 365.0 * SECONDS_PER_DAY # a bit optimistic, eh?

        if changed_ago > SECONDS_PER_YEAR:
            changed_time =  "%0.08f years" % (changed_ago / SECONDS_PER_YEAR)
        elif changed_ago > SECONDS_PER_DAY:
            changed_time =  "%0.05f days" % (changed_ago / SECONDS_PER_DAY)
        elif changed_ago > SECONDS_PER_HOUR:
            changed_time =  "%0.03f hours" % (changed_ago / SECONDS_PER_HOUR)
        elif changed_ago > SECONDS_PER_MINUTE:
            changed_time =  "%0.02f mins" % (changed_ago / SECONDS_PER_MINUTE)
        else:
            changed_time =  "%0.0f sec" % changed_ago

        return '%s (%s)' % (MqttData.value_text(self), changed_time)

class MqttGroup(object):
    def __init__(self, params):
        self.name = params['name']
        self.messages = {}
        for data in params['messages']:
            if 'timed' in data.keys() and data['timed']:
                mqtt_data = MqttTimedData(data)
            else:
                mqtt_data = MqttData(data)
            self.messages[mqtt_data.topic] = mqtt_data

        self.divider = None
        if 'divider' in params.keys():
            self.divider = params['divider']

    def update(self, msg):
        if msg.topic in self.messages:
            self.messages[msg.topic].update(msg.payload)

    def drawHeader(self):
        ''' Return the widget that draws at the top of the widget and represents this switch's status. '''
        pile = urwid.Pile([])

        pile.contents.append((urwid.AttrMap(urwid.Text(self.name), 'title'), pile.options()))

        if self.divider:
            pile.contents.append((urwid.Divider(u'\u2500'), pile.options()))

        return pile

    def draw(self):
        ''' Return the widget that describes this machine, and all of its messages. '''
        widgets = [self.drawHeader()]

        for message in self.messages.values():
            widgets.append(message.draw())

        pile = urwid.Pile(widgets)
        if self.ok():
            return urwid.LineBox(pile)
        else:
            return urwid.AttrMap(urwid.LineBox(pile), 'warn')

    def ok(self):
        for message in self.messages.values():
            if message.ok():
                return True
        return False

class MqttWidget(urwid.Pile):
    ''' Class used to draw the data from the Printer. '''
    def __init__(self, params):
        urwid.Pile.__init__(self, [])

        self.connected = False

        self.params = params
        self.host = params['host']
        self.machines = []
        for machine in params['machines']:
            self.machines.append(MqttGroup(machine))

        self.cols = 1
        if 'columns' in params.keys():
            self.cols = params['columns']

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
        for item in self.machines:
            item.update(msg)
        self.stats_lock.release()

    def getPalette(self):
        ''' Used to populate the pallete. '''
        return [
            ('good', 'light green', '', '', 'light green', ''),
            ('stale', 'light red', '', '', 'light red', ''),
        ]

    def update(self, loop, data):
        rows = []

        connected = "Disconnected"
        if self.connected:
            connected = "Connected"
        rows.append((urwid.AttrMap(urwid.Text('Mqtt(%s): %s' % (self.host, connected)), 'title'), self.options()))

        self.stats_lock.acquire(True)

        if self.cols <= 1:
            for row in self.machines:
                rows.append((row.draw(), self.options()))
        else:
            cols = []
            for row in self.machines:
                cols.append(row.draw())
                if len(cols) == self.cols:
                    rows.append((urwid.Columns(cols), self.options()))
                    cols = []
            if cols:
                rows.append((urwid.Columns(cols), self.options()))

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
        for machine in self.machines:
            if not machine.ok():
                return "%s is not OK" % machine.name

        return None


