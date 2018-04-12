#!/usr/bin/python

import evdev

import threading
import urwid
import os
import sys

#########################################################
# Display stuff
#########################################################

quit = False

class Button(object):
    def __init__(self, params):
        self.name = params['name']
        self.command = params['command']
        self.minx = params['minx']
        self.maxx = params['maxx']
        self.miny = params['miny']
        self.maxy = params['maxy']

        self.isPushed = False
        self.pushTimer = None

    def inBounds(self, x, y):
        return x >= self.minx and \
               x <= self.maxx and \
               y >= self.miny and \
               y <= self.maxy

    def fire(self):
        # To use the recycle command, you have to have a script that catches this return value
        if 'recycle' in self.command:
            global quit
            quit = True
        if 'reboot' in self.command or 'poweroff' in self.command:
            os.system(self.command)
            sys.exit(2)

    def pushed(self):
        self.isPushed = True
        self.pushTimer = threading.Timer(3.0, self.fire)
        self.pushTimer.start()

    def released(self):
        self.isPushed = False
        if self.pushTimer is not None:
            self.pushTimer.cancel()
            self.pushTimer = None

    def draw(self):
        if self.isPushed:
            color = 'pushed'
        else:
            color = 'idle'

        button = urwid.LineBox(urwid.Text((color, self.name), align="center"))
        return button

class DebugTouchWidget(object):
    def __init__(self):
        self.x = 0
        self.y = 0
        self.pushed = False
        self.debug_lock = threading.Lock()

    def setx(self, x):
        self.debug_lock.acquire(True)
        self.x = x
        self.debug_lock.release()

    def sety(self, y):
        self.debug_lock.acquire(True)
        self.y = y
        self.debug_lock.release()

    def setpushed(self, pushed):
        self.debug_lock.acquire(True)
        self.pushed = pushed
        self.debug_lock.release()

    def draw(self):
        ''' Return the widget that describes this machine, and all of its messages. '''
        self.debug_lock.acquire(True)
        pushed = 'idle'
        if self.pushed:
            pushed = 'pushed'

        widget = urwid.Columns([urwid.Text((pushed, u"X: %d" % self.x)), urwid.Text((pushed, u"Y: %d" % self.y))])
        self.debug_lock.release()
        return widget

class EventEmitter(object):
    def __init__(self, callback):
        self.callback = callback
        self.reset()

    def reset(self):
        self.x = None
        self.y = None
        self.isPushed = None

    def checkAndEmit(self):
        if self.x is not None and self.y is not None and self.isPushed is not None:
            keys = [('mouse press', self.isPushed, self.x, self.y)]
            self.callback(keys)
            if not self.isPushed:
                self.reset()

    def setX(self, x):
        self.x = x
        self.checkAndEmit()

    def setY(self, y):
        self.y = y
        self.checkAndEmit()

    def push(self, pushed):
        self.isPushed = pushed
        self.checkAndEmit()

class TouchWidget(urwid.Pile):
    ''' Class used to draw the data from the Printer. '''
    def __init__(self, params):
        urwid.Pile.__init__(self, [])

        self.devicename = params['device']
        self.device = None
        self.connected = False

        self.debug = False
        if 'debug' in params.keys():
            self.debug = params['debug']

        self.debugWidget = DebugTouchWidget()

        self.buttons = []
        for button in params['buttons']:
            self.buttons.append(Button(button))


    def getPalette(self):
        ''' Used to populate the pallete. '''
        return [
            ('idle', 'light green', '', '', 'light green', ''),
            ('pushed', 'light red', '', '', 'light red', ''),
        ]

    def update(self, loop, data):
        if quit:
            raise urwid.ExitMainLoop()
        rows = []

        connected = "Disconnected"
        if self.connected:
            connected = "Connected"
        if self.debug:
            rows.append((urwid.AttrMap(urwid.Text('Controls(%s): %s' % (self.devicename, connected)), 'title'), self.options()))
        else:
            rows.append((urwid.AttrMap(urwid.Text('Controls'), 'title'), self.options()))

        cols = []
        for button in self.buttons:
            cols.append(button.draw())
        rows.append((urwid.Columns(cols), self.options()))

        if self.debug:
            rows.append((self.debugWidget.draw(), self.options()))

        self.contents = rows
        loop.set_alarm_in(0.1, self.update)

    def onTouch(self, keys):
        for key in keys:
            event, pushed, x, y = key
            for button in self.buttons:
                if button.inBounds(x, y):
                    if pushed:
                        button.pushed()
                    else:
                        button.released()

    def start(self, loop):
        ''' Called to add the initial processes to the loop.'''

        self.eventEmitter = EventEmitter(self.onTouch)

        def do():
            self.connected = True
            self.device = evdev.InputDevice(self.devicename)
            for event in self.device.read_loop():
                if event.type == evdev.ecodes.EV_KEY:
                    if event.code == evdev.ecodes.BTN_TOUCH:
                        # Touch or release of touch screen
                        self.debugWidget.setpushed(event.value)
                        self.eventEmitter.push(event.value)
                if event.type == evdev.ecodes.EV_ABS:
                    if event.code == evdev.ecodes.ABS_X:
                        # X location
                        self.debugWidget.setx(event.value)
                        self.eventEmitter.setX(event.value)
                    elif event.code == evdev.ecodes.ABS_Y:
                        # Y location
                        self.debugWidget.sety(event.value)
                        self.eventEmitter.setY(event.value)

        t = threading.Thread(target=do, args=())
        t.setDaemon(True)
        t.start()
        self.update(loop, None)

    def getError(self):
        ''' return if there is a problem that I can detect. '''
        return None

