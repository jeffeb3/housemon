#!/usr/bin/env python

import sys
import commands
import socket
import threading
import urwid

#########################################################
# Simple utilities
#########################################################

def Ping(host):
    """
    Ping the host, to determine upiness.
    """
    command = "ping -c 1 -w 1 -W 1 " + host
    (rv, text) = commands.getstatusoutput(command)
    time = None
    for line in text.split('\n'):
        for word in line.split():
            if word.startswith('time='):
                time = word.split('=')[1]

    ok = rv == 0
    return (ok, time)

def HostByName(name):
    """
    returns the ip (as a string) of the host you are trying to find.
    """
    try:
        return socket.gethostbyname(name)
    except socket.gaierror:
        return None

def IpAsync(host, callback):
    """
    Call the callback when the results are back from the query.
    """
    def do(host, callback):
        ip = HostByName(host)
        if ip:
            StatsAsync(ip, callback)

    t = threading.Thread(target=do, args=(host, callback))
    t.setDaemon(True)
    t.start()
    return t

def StatsAsync(ip, callback):
    """
    Call the callback when the results are back from the query.
    """
    def do(ip, callback):
        rv, time = Ping(ip)
        callback(None, ip, rv, time)

    t = threading.Thread(target=do, args=(ip, callback))
    t.setDaemon(True)
    t.start()
    return t

#########################################################
# Display stuff
#########################################################

class Endpoint(object):
    '''
    Widget that displays information about a single "computer" or network interface.

    Used in a display of a network map.
    '''
    def __init__(self, map):
        '''
        Init
        Attributes read from the map:
            :host: The hostname of the endpoint.
            :ip: The ip address (v4) if the hostname won't resolve.
        '''
        self.host = None
        if 'host' in map.keys():
            self.host = map['host']

        self.ip = None
        if 'ip' in map.keys():
            self.ip = map['ip']

        self.optional = None
        if 'optional' in map.keys():
            self.optional = map['optional']

        self.ping = None
        self.stats_lock = threading.Lock()

        # this is used to draw multiple endpoints with different background colors
        self.row = ''

    def draw(self, host=None):
        ''' Return the widget that draws at the top of the widget and represents this switch's status. '''
        # Let the user define their own hostname for displaying.
        if not host:
            host = self.host

        self.stats_lock.acquire(True)
        cols = []
        if host:
            cols.append(urwid.Text(host))
        else:
            cols.append(urwid.Text(self.host))
        cols.append(urwid.Text('IP: %s' % self.ip))
        if self.ping:
            if float(self.ping) > 100.0:
                cols.append(urwid.AttrMap(urwid.Text('Ping: %sms' % self.ping), 'awful_ping' + self.row))
            elif float(self.ping) > 10.0:
                cols.append(urwid.AttrMap(urwid.Text('Ping: %sms' % self.ping), 'slow_ping' + self.row))
            elif float(self.ping) > 1.0:
                cols.append(urwid.AttrMap(urwid.Text('Ping: %sms' % self.ping), 'ok_ping' + self.row))
            else:
                cols.append(urwid.AttrMap(urwid.Text('Ping: %sms' % self.ping), 'fast_ping' + self.row))

        else:
            cols.append(urwid.Text('Ping: None'))

        w = urwid.Columns(cols)
        if None == self.ping:
            if self.optional:
                w = urwid.AttrMap(w, 'optional' + self.row)
            else:
                w = urwid.AttrMap(w, 'warn' + self.row)
        else:
            w = urwid.AttrMap(w, 'ok' + self.row)
        self.stats_lock.release()
        return w

    def getData(self):
        ''' Start the process of updating the statistics for this endpoint. '''
        if self.host and not self.ip:
            IpAsync(self.host, self.stats_cb)

        if self.ip:
            StatsAsync(self.ip, self.stats_cb)

    # callback
    def stats_cb(self, host, ip, rv, time):
        ''' Gets called when the pinger returns some results. '''
        self.stats_lock.acquire(True)
        self.ip = ip
        if rv:
            self.ping = time
        else:
            self.ping = None
        self.stats_lock.release()

    def ok(self):
        self.stats_lock.acquire(True)
        ok = self.ping != None
        self.stats_lock.release()
        return ok

    def getError(self):
        return None

class Switch(Endpoint):
    '''
    Widget that displays information about a switch or router and it's children.

    Used in a display of a network map.
    '''
    def __init__(self, map):
        '''
        Init
        Attributes read from the map:
            :children: a list of Switch or Endpoint children that are connected only because of this switch
            :host: The hostname if this is a router. None if this is an unmanaged switch
            :ip: The ip address (v4) if the hostname won't resolve.
        '''
        Endpoint.__init__(self, map)

        self.name = None
        if 'name' in map.keys():
            self.name = map['name']

        if not self.name and not self.host and not self.ip:
            print "You have to name the switch something."

        self.cols = 1
        if 'columns' in map.keys():
            self.cols = map['columns']

        self.children = []

        self.divider = None
        if 'divider' in map.keys():
            self.divider = map['divider']

        i = 0
        if 'children' in map.keys():
            for child_map in map['children']:
                if 'children' in child_map.keys():
                    self.children.append(Switch(child_map))
                else:
                    self.children.append(Endpoint(child_map))
                    self.children[-1].row = '_%d' % (i % 2)
                    i += 1

    def getData(self):
        ''' Start the process of updating the statistics for this switch. '''
        Endpoint.getData(self)
        for child in self.children:
            child.getData()

    def drawHeader(self):
        ''' Return the widget that draws at the top of the widget and represents this switch's status. '''
        pile = urwid.Pile([])
        if self.host or self.ip:
            pile.contents.append((Endpoint.draw(self, host=self.name), pile.options()))
        else:
            pile.contents.append((urwid.AttrMap(urwid.Text(self.name), 'title'), pile.options()))

        if self.divider:
            pile.contents.append((urwid.Divider(u'\u2500'), pile.options()))

        return pile

    def draw(self):
        ''' Return the widget that describes this switch, and all of it's children. '''
        widgets = [self.drawHeader()]

        if self.cols <= 1:
            for child in self.children:
                widgets.append(child.draw())
        else:
            cols = []
            for child in self.children:
                cols.append(child.draw())
                if len(cols) == self.cols:
                    widgets.append(urwid.Columns(cols))
                    cols = []
            if cols:
                widgets.append(urwid.Columns(cols))


        pile = urwid.Pile(widgets)
        if self.ok():
            return urwid.LineBox(pile)
        else:
            return urwid.AttrMap(urwid.LineBox(pile), 'warn')

    def ok(self):
        ''' return True if we think we are all OK. '''
        # in this case, ok is if any of my children are present.
        for child in self.children:
            if child.ok():
                return True

        return False

    def getError(self):
        for child in self.children:
            err = child.getError()
            if err:
                return err
        if not self.ok():
            return "%s is not OK" % self.name
        return None

class NetworkMap(urwid.Pile):
    '''
    Network as a map.
    '''
    def __init__(self, map):
        '''
        Toplevel map of the network
        :map: dict of stuff. Loaded from yaml, probably. no docs yet (unless I did them, and didn't update this doc).
        '''
        urwid.Pile.__init__(self, [])

        if not 'net_ip' in map.keys() or \
           not 'net_host' in map.keys() or \
           not 'routers' in map.keys():
            raise InputError("This isn't configured properly. It's probably my fault, sorry. I give up.")

        self.children = []
        for router_map in map['routers']:
            self.children.append(Switch(router_map))

        self.ip = map['net_ip']
        self.host = map['net_host']

        self.ping_ip = None
        self.lookup = None
        self.stats_lock = threading.Lock()

    def drawHeader(self):
        ''' Return the widget that draws at the top of the widget and represents this switch's status. '''

        self.stats_lock.acquire(True)
        cols = []
        # cols.append(urwid.Text('Network Map'))
        if self.ping_ip:
            cols.append(urwid.AttrMap(urwid.Text('Connection: GOOD (%s: %s)' % (self.ip, self.ping_ip)), 'ok'))
        else:
            cols.append(urwid.AttrMap(urwid.Text('Connection: BAD (%s)' % (self.ip)), 'warn'))

        if self.lookup:
            cols.append(urwid.AttrMap(urwid.Text('DNS: GOOD (%s -> %s)' % (self.host, self.lookup)), 'ok'))
        else:
            cols.append(urwid.AttrMap(urwid.Text('DNS: BAD (%s)' % (self.host)), 'warn'))

        w = urwid.Columns(cols)
        if None == self.ping_ip or None == self.lookup:
            w = urwid.AttrMap(w, 'warn')
        else:
            w = urwid.AttrMap(w, 'ok')
        self.stats_lock.release()
        return w


    def getPalette(self):
        ''' Used to populate the pallete. '''
        palette = [
        ]
        fg_colors = {
            'ok': ('light green', 'light green'),
            'warn': ('light red', 'light red'),
            'optional': ('dark gray', 'dark gray'),
            'awful_ping': ('dark red', '#f00'),
            'slow_ping': ('yellow', '#c80'),
            'ok_ping': ('dark green', '#8c0'),
            'fast_ping': ('light green', '#0f0'),
        }

        bg_colors = {
            '_0': ('', ''),
            '_1': ('', 'g10'),
            '': ('','')
        }

        for status, fgs in fg_colors.items():
            for row, bgs in bg_colors.items():
                theme = status + row
                palette.append((theme, fgs[0], bgs[0], '', fgs[1], bgs[1]))

        return palette

    def getData(self, loop, user_data):
        ''' Start updating each endpoint's data '''
        for child in self.children:
            child.getData()

        IpAsync(self.host, self.lookup_cb)

        StatsAsync(self.ip, self.ping_cb)

        loop.set_alarm_in(15.0, self.getData)

    def getError(self):
        ''' Return a human readable string of some normal problems. '''
        for child in self.children:
            # Everything is broken...
            if not child.ok():
                return "You aren't connected to the router. There might be zombies in the house."

        for child in self.children:
            # One switch is broken
            err = child.getError()
            if err:
                return err

        if self.ping_ip == None:
            return "The Intenet is missing. Check for zombies. Better yet, stay inside."

        if self.lookup == None:
            return "There is a problem with name lookups on the Internet. Stupid IT guy."

        # I can't diagnose more complicated problems.
        return None

    # callback
    def ping_cb(self, host, ip, rv, time):
        ''' Gets called when the pinger returns some results. '''
        self.stats_lock.acquire(True)
        if rv:
            self.ping_ip = time
        else:
            self.ping_ip = None
        self.stats_lock.release()

    def lookup_cb(self, host, ip, rv, time):
        ''' Gets called when the nslookup and ping return. '''
        self.stats_lock.acquire(True)
        if rv:
            self.lookup = ip
        else:
            self.lookup = None
        self.stats_lock.release()

    def draw(self, loop, data):
        ''' This updates the widgets used in the pinger part of the display. '''
        machine_texts = []

        machine_texts.append((self.drawHeader(), self.options()))
        for child in self.children:
            machine_texts.append((child.draw(), self.options()))
        self.contents = machine_texts
        loop.set_alarm_in(0.5, self.draw)

    def start(self, loop):
        ''' Called to add the initial processes to the loop.'''
        self.getData(loop, None)
        self.draw(loop, None)

if __name__ == '__main__':
    # some test code

    # callback
    def cb(host, ip, rv, time):
        print host,ip,rv,time

    threads = []
    for host in sys.argv[1:]:
        threads.append(StatsAsync(host, cb))

    print 'spawned everything'

    # wait for everyone.
    for t in threads:
        t.join()
