#!/usr/bin/env python
"""
    As far as I am aware cwiid is only avaiable on linux
    The requirements are as follows:
    A working linux bluetooth device!! (http://www.wiili.org/index.php/Compatible_Bluetooth_Devices)
    ====================
    Bluetooth libraries
    ====================
    bluez-utils
    libbluetooth-dev  
    libbluetooth2
 
    ====================
    cwiid software
    ====================
    libcwiid1
    libcwiid1-dev
    python-cwiid


    The below python OSC libraries can be installed using pip.
    The version numbers indicate what I have installed on my system (as
    reported by '>>> pip freeze'
    ====================
    OSC libraries
    ====================
    SimpleOSC==0.3
    pyOSC==0.3.5b-5294

    Pitch and roll calculations were learned from the following document:
    http://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=7&ved=0CE4QFjAG&url=http%3A%2F%2Fwww.cmpe.boun.edu.tr%2Fmedialab%2FVW%2FWiimote_Linux_integration.pdf&ei=XwnJTsVzkISFB63chL4P&usg=AFQjCNFMVd34Tc4_zWO4FjaSiOKrynEyfg

    
"""
# Standard library imports
from __future__ import division
import sys
from time import sleep
from math import atan, cos, pi

# Third party libraries
from OSC import OSCClient, OSCMessage, OSCClientError
import cwiid
from cwiid import Wiimote


def listen(w, my_map, freq=0.01):
    """
        Receives an initiliased wiimote to talk to, a wiimote my_mapping object, 
        along with a frequency with which to send messages to the client 
    """
    try:
        while True:   
            sleep(freq)
            #w.rpt_mode = cwiid.RPT_EXT + cwiid.RPT_ACC + cwiid.RPT_BTN
            #print w.state          
            my_map.update_state(w.state)
    except KeyboardInterrupt, e:
        return w
    except OSCClientError, e:
        print("OSC client error has occurred: '%s' \n Stop listening..." % e)
        return w

def setup():
    """
        Makes the connection with the wiimote
    """
    ready = raw_input("Press 1 and 2 simultaenously on the wiimote. \n Click any key when done")
    try:
        w = Wiimote()
    except RuntimeError, e:
        print("Error has occured: '%s'. Please ensure wiimote is active by \
            pressing 1 and 2 simulataenoulsy till the control lights up." % e)
        raise e
    w.rpt_mode = cwiid.RPT_ACC | cwiid.RPT_NUNCHUK | cwiid.RPT_BTN
    remote_cal = w.get_acc_cal(cwiid.EXT_NONE)
    nunchuk_cal = w.get_acc_cal(cwiid.EXT_NUNCHUK)
            
    return w, remote_cal, nunchuk_cal

parse_state = lambda state: dict([('buttons', state['buttons']) ,('acc', state['acc']), ('nunchuk', state['nunchuk'])])


class Wiimy_mapping(object):
    """
        Class designed to send the wiimote state via OSC.
        Sends acc, nunchuk and buttons state messages from cwiid.
        The update state 
    """


    def __init__(self, address=('localhost', 5600)):
        """ Set up a connection to the address specified. """ 
        self.client = OSCClient()
        self.address = address
        self.prev_state = None


    def set_acc_cal(self, remote_cal, nunchuk_cal):
        """
            Receives the initial calibration values for
            the remote and the nunchuk. These are used to 
            calculate pitch and roll :)

        """
        self.cal_r_x = remote_cal[0][0] /(remote_cal[1][0] - remote_cal[0][0])
        self.cal_r_y = remote_cal[0][1] /(remote_cal[1][1] - remote_cal[0][1])
        self.cal_r_z = remote_cal[0][2] /(remote_cal[1][2] - remote_cal[0][2])
        self.cal_n_x = nunchuk_cal[0][0] /(nunchuk_cal[1][0] - nunchuk_cal[0][0])
        self.cal_n_y = nunchuk_cal[0][1] /(nunchuk_cal[1][1] - nunchuk_cal[0][1])
        self.cal_n_z = nunchuk_cal[0][2] /(nunchuk_cal[1][2] - nunchuk_cal[0][2])

    def update_state(self, state):
        """
            
        """
        state = parse_state(state)
        if self.prev_state:
           for k in state:
               if not self.prev_state[k] == state[k]:
                   getattr(self, k)(state[k])
           self.prev_state = state     
        else:
            self.prev_state = state
            for k in state.keys():
                getattr(self, k)(state[k])
        
        
    def acc(self, state):
        """ 
            Extract acceleration, pitch and roll from the wiimote.

        """
        # Need to calculate pitch and roll here...
        a_x = state[0] - self.cal_r_x
        a_y = state[1] - self.cal_r_y
        a_z = state[2] - self.cal_r_z
        roll = atan(a_x/a_z)
        if a_z < 0.0:
            if a_x > 0.0:
                roll += pi
            else:
                roll += (pi * -1)
        roll *= -1
        pitch = atan(a_y/a_z*cos(roll))
        msg = OSCMessage('/wii/acc')
        msg.append((a_x, a_y, a_z))
        self.client.sendto(msg=msg, address=self.address)
        msg = OSCMessage('/wii/orientation')
        msg.append((pitch, roll))
        self.client.sendto(msg=msg, address=self.address)

    def buttons(self, state):
        """ Extract button A, minus and plus only. """

        msg_a = OSCMessage('/wii/button/a')
        msg_minus = OSCMessage('/wii/button/minus')
        msg_plus = OSCMessage('/wii/button/plus')
        a = 0
        minus = 0
        plus = 0
        if state in (8, 24, 4104, 4120):
            a = 1
        if state in (16, 24, 4104, 4120):
            minus = 1
        if state in (4096, 24, 4104, 4120):
            plus = 1
        msg_a.append(a)
        msg_minus.append(minus)
        msg_plus.append(plus)
        self.client.sendto(msg=msg_a, address=self.address)
        self.client.sendto(msg=msg_minus, address=self.address)
        self.client.sendto(msg=msg_plus, address=self.address)

    def nunchuk(self, state):
        """ 
            Extract acceleration, pitch, roll and both buttons 
            from the nunchuk.

        """
        # Need to calculate pitch and roll here...
        a_x = state['acc'][0] - self.cal_n_x
        a_y = state['acc'][1] - self.cal_n_y
        a_z = state['acc'][2] - self.cal_n_z
        roll = atan(a_x/a_z)
        pitch = atan(a_y/a_z*cos(roll))
        msg = OSCMessage('/nunchuk/acc')
        msg.append((a_x, a_y, a_z))
        self.client.sendto(msg=msg, address=self.address)
        msg = OSCMessage('/nunchuk/orientation')
        msg.append((pitch, roll))
        self.client.sendto(msg=msg, address=self.address)
        msg = OSCMessage('/nunchuk/joystick')
        msg.append(state['stick'])
        self.client.sendto(msg=msg, address=self.address)
        msg_z = OSCMessage('/nunchuk/button/z')
        msg_c = OSCMessage('/nunchuk/button/c')
        z = 0
        c = 0
        if state['buttons'] in [1, 3]:
            z = 1
        if state['buttons'] in [2,3]:
            c = 1
        msg_z.append(z)
        msg_c.append(c)
        self.client.sendto(msg=msg_z, address=self.address)
        self.client.sendto(msg=msg_c, address=self.address)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        print ("Expecting arg1 to be server address and arg2 to be the port")
        address = (sys.argv[1], sys.argv[2])
    else:
        add = ('localhost', 5600)
    my_map = Wiimy_mapping(add)
    (w, remote_cal, nunchuk_cal) = setup()
    my_map.set_acc_cal(remote_cal, nunchuk_cal)
    listen(w, my_map)  
        
