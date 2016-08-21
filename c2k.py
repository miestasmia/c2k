#!/usr/bin/env python2

"""
Copyright (c) 2015 Mia Nordentoft

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated  documentation files (the "Software"),  to deal in
the Software  without restriction,  including without limitation  the rights to
use,  copy, modify, merge, publish,  distribute, sublicense, and/or sell copies
of the Software,  and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice  and this permission notice shall be included in all
copies or substantial portions of the Software.

THE  SOFTWARE IS  PROVIDED  "AS IS",  WITHOUT WARRANTY OF ANY KIND,  EXPRESS OR
IMPLIED,  INCLUDING  BUT  NOT  LIMITED  TO  THE  WARRANTIES OF MERCHANTABILITY,
FITNESS  FOR A PARTICULAR PURPOSE  AND NONINFRINGEMENT.  IN NO EVENT  SHALL THE
AUTHORS  OR  COPYRIGHT  HOLDERS  BE  LIABLE FOR ANY  CLAIM , DAMAGES  OR  OTHER
LIABILITY,  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,  ARISING FROM,
OUT OF  OR IN CONNECTION WITH THE SOFTWARE  OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import pygame, subprocess, time, os, sys, json, curses, math, signal
from pymouse import PyMouse
from pykeyboard import PyKeyboard

DRAW_FPS  = 20
WATCH_FPS = 60
TRIGGER_SYMBOLS = "!~@*"

dirname = os.path.dirname(__file__)
sys.path.append(os.path.join(dirname, os.path.pardir))

def signal_handler(signal, frame):
    sys.exit(130)
signal.signal(signal.SIGINT, signal_handler)

def draw_controller(joystick, text):
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0)

    clock = pygame.time.Clock()

    while True:
        pygame.event.pump()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

        for i, t in enumerate(text):
            stdscr.addstr(i, 0, t);
        j = len(text) + 1

        try:
            for i in xrange(joystick.get_numaxes()):
                val = joystick.get_axis(i)
                left  = ("#" * int(round(max(-val, 0) * 8))).rjust(8)
                right = ("#" * int(round(max(val, 0)  * 8))).ljust(8)

                stdscr.addstr(i + j, 0, "Axis %s" % i)
                stdscr.addstr(i + j, 8, "[%s|%s]" % (left, right))

            for i in xrange(joystick.get_numbuttons()):
                if joystick.get_button(i):
                    x = "X"
                else:
                    x = " "

                stdscr.addstr(i + j, 30, "Button %s" % i)
                stdscr.addstr(i + j, 40, "[%s]" % x)

            stdscr.refresh()
            clock.tick(DRAW_FPS)
        finally:
            curses.echo()
            curses.nocbreak()
            curses.endwin()

def watch_controller(joystick, bindings, controller):
    global mousePos, timestamp, lastTimestamp, deltaTime

    # Load output
    mouse = PyMouse()
    keyboard = PyKeyboard()

    clock = pygame.time.Clock()

    mousePos = (0, 0)

    lastTimestamp = 0
    timestamp = 0
    deltaTime = timestamp - lastTimestamp

    controller_watch = {}
    controller_watch_previous = {}
    for name, input in controller['inputs'].iteritems():
        if input['type'] == 'button':
            controller_watch[name] = joystick.get_button(input['id'])
        elif input['type'] == 'axis':
            controller_watch[name] = joystick.get_axis(input['id'])

    key_watch = {}
    def get_key(key):
        if key in key_watch:
            return key_watch[key]
        else:
            return False

    def handle_action(action, input):
        global mousePos, timestamp, deltaTime

        type = action['type']

        if type == 'keyboard_tap':
            keyboard.tap_key(action['key'])
            key_watch[ action['key'] ] = False
        elif type == 'keyboard_down':
            keyboard.press_key(action['key'])
            key_watch[ action['key'] ] = True
        elif type == 'keyboard_up':
            keyboard.release_key(action['key'])
            key_watch[ action['key'] ] = False
        elif type == 'if':
            if eval(action['if'], globals(), {
                'x': controller_watch[input],
                'b': controller_watch
            }):
                handle_actions(action['do'], input)
            elif 'else' in action:
                handle_actions(action['else'], input)
        elif type == 'if_key':
            if get_key(action['key']) == action['is']:
                handle_actions(action['do'], input)
            elif 'else' in action:
                handle_actions(action['else'], input)
        elif type == 'move_mouse_h_proportional':
            speed = controller_watch[input]
            mouseX, mouseY = mousePos
            mouseX += speed * action['factor'] * deltaTime
            mousePos = (mouseX, mouseY)
            mouse.move(*mousePos)
        elif type == 'move_mouse_v_proportional':
            speed = controller_watch[input]
            mouseX, mouseY = mousePos
            mouseY += speed * action['factor'] * deltaTime
            mousePos = (mouseX, mouseY)
            mouse.move(*mousePos)
        elif type == 'scroll':
            x = 0
            y = 0

            if 'x' in action:
                x = action['x']
            if 'y' in action:
                y = action['y']

            mouse.scroll(y, x)
        elif type == 'do_every':
            if not 'last' in action:
                action['last'] = 0

            if timestamp - action['last'] >= action['every']:
                handle_actions(action['do'], input)
                action['last'] = timestamp
        elif type == 'mouse_down':
            mouse.press(mousePos[0], mousePos[1], action['button'])
        elif type == 'mouse_up':
            mouse.release(mousePos[0], mousePos[1], action['button'])
        elif type == 'mouse_click':
            n = 1
            if 'n' in action:
                n = action['n']
            mouse.click(mousePos[0], mousePos[1], action['button'], n)

    def handle_actions(actions, input):
        if isinstance(actions, list):
            for action in actions:
                handle_action(action, input)
        elif isinstance(actions, dict):
            handle_action(actions, input)

    while True:
        timestamp = time.time()
        deltaTime = timestamp - lastTimestamp

        pygame.event.pump()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

        for name, value in controller_watch.iteritems():
            controller_watch_previous[name] = value

            input = controller['inputs'][name]

            if input['type'] == 'button':
                controller_watch[name] = joystick.get_button(input['id'])
            elif input['type'] == 'axis':
                val = joystick.get_axis(input['id'])

                if ('force_positive' in input and input['force_positive']):
                    val = (val + 1) / 2

                controller_watch[name] = val

        mousePos = mouse.position()

        for binding, actions in bindings.iteritems():
            trigger = ""

            if binding[0] in TRIGGER_SYMBOLS:
                trigger = binding[0]
                binding = binding[1:]

            value = controller_watch[binding]
            previous_value = controller_watch_previous[binding]
            changed = value != previous_value

            do_trigger = False

            if trigger == "": # button down
                do_trigger = value and changed
            elif trigger == "!": # button up
                do_trigger = not value and changed
            elif trigger == "~": # button up/down
                do_trigger = changed
            elif trigger == "@": # always
                do_trigger = True
            elif trigger == "*": # always when down
                do_trigger = value

            if do_trigger:
                handle_actions(actions, binding)

        lastTimestamp = timestamp

        clock.tick(WATCH_FPS)

euid = os.geteuid()
if euid != 0:
    print "error: c2k must be run as root"
    sys.exit(126)

pygame.init()
pygame.joystick.init();
joysticks = [ pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count()) ]

print "Please select a controller"
print "Available controllers:"

for joystick in joysticks:
    print "(%s) %s" % (joystick.get_id(), joystick.get_name())

joystick = None

while joystick is None:
    joystick_id = raw_input("Controller id: ")
    try:
        joystick_id = int(joystick_id)
    except ValueError:
        print "Invalid controller id"
        continue

    if joystick_id < len(joysticks):
        joystick = joysticks[joystick_id]
    else:
        print "There's no controller with that id"

with open(os.path.join(dirname, 'controllers.json')) as controller_config_file:
    controller_config = json.load(controller_config_file)

bindings_files = os.listdir(os.path.join(dirname, 'bindings'))

joystick.init()

if not joystick.get_name() in controller_config:
    draw_controller(joystick, [
        "%s has no config. Please create one in controllers.json" % joystick.get_name(),
        "You can watch your controller live using the below meters:"])
else:
    print "Please select a binding"
    print "Available bindings:"

    for filename in bindings_files:
        with open(os.path.join(dirname, 'bindings', filename)) as file:
            file_data = json.load(file)

        if not joystick.get_name() in file_data['bindings']:
            continue

        print "* %s (%s)" % (file_data['name'], filename[:-5])

    binding = None
    while binding is None:
        binding_id = raw_input("Binding name: ")

        if binding_id + ".json" in bindings_files:
            with open(os.path.join(dirname, 'bindings', binding_id + ".json")) as file:
                binding = json.load(file)['bindings'][ joystick.get_name() ]
        else:
            print "There's no binding with that id"

    watch_controller(joystick, binding, controller_config[ joystick.get_name() ])
