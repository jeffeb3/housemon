#!/usr/bin/env python

import pinger, printer, mqtt
import urwid
import threading
import yaml

def event(key):
    if key in ['q', 'Q']:
        raise urwid.ExitMainLoop()

def set_status(state):
    status.set_text([u"Status: ", state])

def query_status(loop, widgets):
    final_error = 'I think things are OK, but I have no brain, so use yours.'
    for wid in widgets:
        error = wid.getError()
        if error:
            final_error = error
            break
    set_status(final_error)
    loop.set_alarm_in(1.0, query_status, widgets)

if __name__ == '__main__':

    # top and bottom fields.
    title = urwid.Text(u"Evil House Monitor v0.1")
    status = urwid.Text(u"Status:")

    # Individual widget objects
    widgets = []
    with open('config.yaml', 'r') as config_file:

        config = yaml.load(config_file)

        net_map = config['network map']
        mqtt_params = config['mqtt']

    widgets.append(pinger.NetworkMap(net_map))
    widgets.append(mqtt.MqttWidget(mqtt_params))

    widgets.append(printer.PrinterWidget('octopi.local','redacted'))

    # Create the color pallete
    palette = [
        ('title', 'light blue', '', '', 'light blue', ''),
    ]

    for wid in widgets:
        palette += wid.getPalette()

    # Create the main loop.
    main_wid = urwid.Pile([title] + [urwid.LineBox(w) for w in widgets] + [status])
    fill = urwid.Filler(main_wid, 'top')
    loop = urwid.MainLoop(fill, palette, unhandled_input=event)
    loop.screen.set_terminal_properties(colors=256)

    # Kick off the updates for each widget.
    for wid in widgets:
        wid.start(loop)

    # start this a little later.
    loop.set_alarm_in(1.0, query_status, widgets)

    loop.run()


