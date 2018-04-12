#!/usr/bin/env python

import pinger, printer, mqtt, touch
import urwid
import threading
import yaml
import time
import os.path
import platform, socket

def event(key):
    if key in ['q', 'Q']:
        raise urwid.ExitMainLoop()

def set_status(state):
    status.set_text([u"Status: ", state])

def update(loop, widgets):
    final_error = 'I think things are OK, but I have no brain, so use yours.'
    for wid in widgets:
        error = wid.getError()
        if error:
            final_error = error
            break
    set_status(final_error)
    set_title()
    loop.set_alarm_in(1.0, update, widgets)

def uptime_text():
    uptime_value = time.time() - uptime_text.start

    SECONDS_PER_MINUTE = 60.0
    SECONDS_PER_HOUR = 60.0 * SECONDS_PER_MINUTE
    SECONDS_PER_DAY = 24.0 * SECONDS_PER_HOUR
    SECONDS_PER_YEAR = 365.0 * SECONDS_PER_DAY # a bit optimistic, eh?

    if uptime_value > SECONDS_PER_YEAR:
        return "%0.08f years" % (uptime_value / SECONDS_PER_YEAR)
    if uptime_value > SECONDS_PER_DAY:
        return "%0.05f days" % (uptime_value / SECONDS_PER_DAY)
    if uptime_value > SECONDS_PER_HOUR:
        return "%0.03f hours" % (uptime_value / SECONDS_PER_HOUR)
    if uptime_value > SECONDS_PER_MINUTE:
        return "%0.02f mins" % (uptime_value / SECONDS_PER_MINUTE)
    return "%0.0f sec" % uptime_value

uptime_text.start = time.time()

def set_title():
    clock.set_text([u'%s' % time.asctime()])
    threads.set_text([u"Threads:\n%d" % threading.active_count()])
    hostname.set_text([u"%s:\n%s" % (platform.node(), socket.gethostbyname(platform.node() + '.local'))])
    uptime.set_text([u"Uptime:\n%s" % uptime_text()])

class WidgetColumns(urwid.Columns):
    def __init__(self, widgets):
        urwid.Columns.__init__(self, [urwid.LineBox(w) for w in widgets])
        self.widgets = widgets

    def getPalette(self):
        palette = []

        for wid in self.widgets:
            palette += wid.getPalette()

        return palette

    def start(self, loop):
        for wid in self.widgets:
            wid.start(loop)

    def getError(self):
        for wid in self.widgets:
            error = wid.getError()
            if error:
                return error
        return None


def createWidget(type, config):
    ''' Big demultiplexer for the different widgets '''
    if type == 'mqtt':
        return mqtt.MqttWidget(config)
    if type == 'network map':
        return pinger.NetworkMap(config)
    if type == 'octoprint':
        return printer.PrinterWidget(config)
    if type == 'touch':
        return touch.TouchWidget(config)
    if type == 'columns':
        subwidgets = []
        for subconfig in config:
            subtype = subconfig.keys()[0]
            subwidgets.append(createWidget(subtype, subconfig[subtype]))
        return WidgetColumns(subwidgets)
    raise TypeError("Invalid top level configuration")

if __name__ == '__main__':

    # top and bottom fields.
    title_name = urwid.Text(u"Evil House Monitor\nv0.1")
    clock = urwid.Text(u"Clock", align="right")
    threads = urwid.Text(u"threads", align="center")
    hostname = urwid.Text(u"hostname", align="center")
    uptime = urwid.Text(u"uptime", align="center")
    title = urwid.Columns([title_name, threads, hostname, uptime, clock])
    set_title()
    status = urwid.Text(u"Status:")

    # config
    if os.path.isfile('config.yaml'):
        config_filename = 'config.yaml'
    else:
        config_filename = 'example/config.yaml'

    # Individual widget objects
    widgets = []
    with open(config_filename, 'r') as config_file:

        config = yaml.load(config_file)

        for widget_config_map in config:
            type = widget_config_map.keys()[0]
            widgets.append(createWidget(type, widget_config_map[type]))

    # Create the color pallete
    palette = [
        ('title', 'light blue', '', '', 'light blue', ''),
    ]

    for wid in widgets:
        palette += wid.getPalette()

    # Create the main loop.
    divider = urwid.Divider(u'\u2500')
    header = urwid.Pile([title, divider])
    body = urwid.Filler(urwid.Pile([urwid.LineBox(w) for w in widgets]), 'top')
    footer = urwid.Pile([divider, status])
    main_wid = urwid.Frame(body, header, footer)
    loop = urwid.MainLoop(main_wid, palette, unhandled_input=event)
    loop.screen.set_terminal_properties(colors=256)

    # Kick off the updates for each widget.
    for wid in widgets:
        wid.start(loop)

    # start this a little later.
    loop.set_alarm_in(1.0, update, widgets)

    loop.run()


