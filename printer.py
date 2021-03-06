#!/usr/bin/env python

import json
import urllib2
import time
import threading
import urwid

def ReadData(url):
    """ Read data from the printer. """
    try:
        data = json.load(urllib2.urlopen(url))
    except:
        return None
    return data

def ReadDataAsync(url, callback):
    def do(url, callback):
        data = ReadData(url)
        callback(data)

    t = threading.Thread(target=do, args=(url, callback))
    t.setDaemon(True)
    t.start()
    return t

#########################################################
# Display stuff
#########################################################

class PrinterWidget(urwid.Pile):
    ''' Class used to draw the data from the Printer. '''
    def __init__(self, params):
        urwid.Pile.__init__(self, [])
        self.machine = params['host']
        self.key = params['key']
        self.stats = {}
        self.stats['state'] = { 'text': 'Unknown' }
        self.stats['temperature'] = { 'bed': {"actual": 0.0, "target": 0.0},
                                    'tool0': {"actual": 0.0, "target": 0.0}}
        self.stats['last_update'] = time.time()
        self.stats_lock = threading.Lock()

    def getPalette(self):
        ''' Used to populate the pallete. '''
        return [
            ('cool', 'light blue', '', '', 'light blue', ''),
            ('warm', 'light magenta', '', '', 'light magenta', ''),
            ('hot', 'light red', '', '', 'light red', ''),
            ('old_data', 'dark red', '', '', 'light red', ''),
        ]

    # callback
    def stats_cb(self, data):
        ''' Gets called when the data returns. '''
        self.stats_lock.acquire(True)
        if data is not None:
            self.stats.update(data)
            self.stats['last_update'] = time.time()
        else:
            self.stats['state']['text'] = 'Unknown'
            self.stats['temperature']['bed']['actual'] = 0.0
            self.stats['temperature']['tool0']['actual'] = 0.0
            self.stats['temperature']['bed']['target'] = 0.0
            self.stats['temperature']['tool0']['target'] = 0.0
        self.stats_lock.release()

    def getData(self, loop, user_data):
        ''' This looks for all the machines, and then puts itself back into the list of things to get called by loop.'''
        ReadDataAsync('http://%s/api/printer?apikey=%s' % (self.machine, self.key), self.stats_cb)
        loop.set_alarm_in(3.0, self.getData)

    def update(self, loop, data):
        ''' This updates the widgets used in the pinger part of the display. '''
        rows = []

        self.stats_lock.acquire(True)
        try:
            status = self.stats['state']['text']
        except KeyError as e:
            status = "Unknown"
        try:
            bed_temp = (float(self.stats['temperature']['bed']['actual']),
                        float(self.stats['temperature']['bed']['target']))
        except KeyError as e:
            bed_temp = (0,0)
        try:
            nozzle_temp = (float(self.stats['temperature']['tool0']['actual']),
                           float(self.stats['temperature']['tool0']['target']))
        except KeyError as e:
            nozzle_temp = (0,0)
        old = (time.time() - self.stats['last_update']) > 22.0
        self.stats_lock.release()

        theme = 'title'
        if old:
            theme = 'old_data'
        rows.append((urwid.AttrMap(urwid.Text('Octoprint: %s' % status), theme), self.options()))

        cols = urwid.Columns([])
        temp = None
        if bed_temp[0] < 30.0:
            temp = 'cool'
        elif bed_temp[0] > 60.0:
            temp = 'hot'
        else:
            temp = 'warm'
        cols.contents.append((urwid.AttrMap(urwid.Text('Bed Temp: %0.1fC / %0.1fC' % bed_temp), temp), cols.options()))
        temp = None
        if nozzle_temp[0] < 100.0:
            temp = 'cool'
        elif nozzle_temp[0] > 200.0:
            temp = 'hot'
        else:
            temp = 'warm'
        cols.contents.append((urwid.AttrMap(urwid.Text('Nozzle Temp:: %0.1fC / %0.1fC' % nozzle_temp), temp), cols.options()))
        rows.append((cols, self.options()))

        self.contents = rows
        loop.set_alarm_in(0.5, self.update)

    def start(self, loop):
        ''' Called to add the initial processes to the loop.'''
        self.getData(loop, None)
        self.update(loop, None)

    def getError(self):
        ''' return if there is a problem that I can detect. '''
        self.stats_lock.acquire(True)
        state = self.stats['state']
        self.stats_lock.release()
        if state['text'] == 'Unknown':
            return "Octoprint server %s is not responding" % self.machine
        return None

if __name__ == '__main__':
    import yaml
    with open('config.yaml', 'r') as config_file:

        cfg = yaml.load(config_file)
        for wid in cfg:
            if wid.keys()[0] == 'octoprint':
                print(ReadData("http://%s/api/printer?apikey=%s" % (wid['octoprint']['host'], wid['octoprint']['key'])))

