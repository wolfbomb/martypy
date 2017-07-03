import six
import struct
from .utils import dict_merge
from .serialclient import SerialClient
from .socketclient import SocketClient
from .testclient import TestClient
from .exceptions import (MartyCommandException,
                         MartyConnectException,
                         MartyConfigException,
                         ArgumentOutOfRangeException)


class Marty(object):
    '''
    High-level client library for Marty the Robot by Robotical Ltd
    '''

    CLIENT_TYPES = {
        'socket' : SocketClient,
        'serial' : SerialClient,
        'test'   : TestClient,
    }

    def __init__(self, url='socket://marty.local',
                 client_types=dict(),
                 default_lifelike=True,
                 *args, **kwargs):
        '''
        Initialise a Marty client class from a url

        Args:
            url: Describes where the Marty can be found and what protocol it's speaking

        Raises:
            MartyConnectException if the client couldn't be initialised
        '''

        proto, _, loc = url.partition('://')

        self.CLIENT_TYPES = dict_merge(self.CLIENT_TYPES, client_types)
        
        if not (proto and loc):
            raise MartyConfigException('Invalid URL format "{}" given'.format(url))

        if proto not in self.CLIENT_TYPES.keys():
            raise MartyConfigtException('Unrecognised URL protocol "{}"'.format(proto))

        # Initialise the client class used to communicate with Marty
        self.client = self.CLIENT_TYPES[proto](proto, loc, *args, **kwargs)

        # To be able to do anything:
        self.enable_safeties(True)
        self.enable_motors(True)

        if default_lifelike:
            self.lifelike_behaviour(True)


    def _pack_uint16(self, num):
        '''
        Pack an unsigned 16 bit int into two 8 bit bytes, little-endian
        Returns:
            tuple(least-sig-byte, most-sig-byte)

        Struct:
            Fmt    C Type                 Python Type    Standard Size
            h      short/uint16           integer        2
        '''
        try:
            data = struct.pack('<H', num)
        except struct.error as e:
            raise ArgumentOutOfRangeException(e)
        return chr(six.byte2int(data[:1])), chr(six.byte2int(data[-1::]))


    def _pack_int16(self, num):
        '''
        Pack a signed 16 bit int into two 8 bit bytes, little-endian
        Returns:
            tuple(least-sig-byte, most-sig-byte)

        Struct:
            Fmt    C Type                 Python Type    Standard Size
            h      short/uint16           integer        2
        '''
        try:
            data = struct.pack('<h', num)
        except struct.error as e:
            raise ArgumentOutOfRangeException(e)
        return chr(six.byte2int(data[:1])), chr(six.byte2int(data[-1::]))


    def _pack_uint8(self, num):
        '''
        Pack an unsigned 8 bit int into one 8 bit byte, little-endian
        Returns:
            bytes
        
        Struct:
            Fmt    C Type                 Python Type    Standard Size
            B      unsigned char/uint8    integer        1
        '''
        try:
            data = struct.pack('<B', num)
        except struct.error as e:
            raise ArgumentOutOfRangeException(e)
        return chr(six.byte2int(data[:1]))


    def _pack_int8(self, num):
        '''
        Pack a signed 8 bit int into one 8 bit unsigned byte, little-endian
        Returns:
            bytes
        
        Struct:
            Fmt    C Type                 Python Type    Standard Size
            b      signed char/int8       integer        1
        '''
        try:
            data = struct.pack('<b', num)
        except struct.error as e:
            raise ArgumentOutOfRangeException(e)
        return chr(six.byte2int(data[:1]))


    def _pack_float(self, num):
        '''
        Pack a float into four bit unsigned byte, little-endian
        Returns:
            tuple(least-sig-byte, less-sig-byte, more-sig-byte, most-sig-byte)
        
        Struct:
            Fmt    C Type                 Python Type    Standard Size
            f      float                  float          4
        '''
        try:
            data = struct.pack('<f', float(num))
        except struct.error as e:
            raise ArgumentOutOfRangeException(e)
        return (chr(six.byte2int([data[0]])),
                chr(six.byte2int([data[1]])),
                chr(six.byte2int([data[2]])),
                chr(six.byte2int([data[3]])))



    def hello(self):
        '''
        Zero joints and wiggle eyebrows
        '''
        return self.client.execute('hello')


    def discover(self):
        '''
        Try and find us some Marties!
        '''
        return self.client.discover()


    SIDE_CODES = {
        'left'    : '\x00',
        'right'   : '\x01',
        'forward' : '\x02',
        'back'    : '\x03',
        'auto'    : '\xff',
    }


    STOP_TYPE = {
        'clear queue'       : '\x00', # clear movement queue only (so finish the current movement)
        'clear and stop'    : '\x01', # clear movement queue and servo queues (freeze in-place)
        'clear and disable' : '\x02', # clear everything and disable motors
        'clear and zero'    : '\x03', # clear everything, and make robot return to zero
        'pause'             : '\x04', # pause, but keep servo and movequeue intact and motors enabled
        'pause and disable' : '\x05', # as 4, but disable motors too
    }


    def stop(self, stop_type=None):
        '''
        Stop motions
        Args:
            stop_type, str, a member of Marty.STOP_TYPE's keys
        Raises:
            MartyCommandException if the stop_type is unknown
        '''
        if stop_type is None:
            stop_type = 'clear and stop'

        try:
            stop = self.STOP_TYPE[stop_type]
        except KeyError:
            raise MartyCommandException("Unknown Stop Type '{}', not in Marty.STOP_TYPE"
                                        "".format(stop_type))

        return self.client.execute('stop', stop)


    def move_joint(self, joint_id, postition, move_time):
        '''
        Move a specific joint to a position
        Args:
            move_time: how long this movement should last, in milliseconds
        '''
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('move_joint',
                                   self._pack_uint8(joint_id),
                                   self._pack_int8(postition),
                                   dur_lsb, dur_msb)


    def lean(self, direction, amount, move_time):
        '''
        Lean over in a direction
        Args:
            direction: 'left' or 'right'
            amount: distance
            move_time: how long this movement should last, in milliseconds
        '''
        side_c = self.SIDE_CODES[direction]
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('lean', side_c,
                                   self._pack_int8(amount),
                                   dur_lsb, dur_msb)


    def walk(self, num_steps=2, start_foot='left', turn=0, step_length=40, move_time=1500):
        '''
        Walking macro
        Args:
            num_steps: int, how many steps to take
            start_foot: 'left' or 'right', start walking with this foot
            turn: How much to turn (-128 to 127). 0 is straight.
            step_length: How far to step (approximately in mm)
            move_time: how long this movement should last, in milliseconds
        '''
        side_c = self.SIDE_CODES[start_foot]
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('walk',
                                   self._pack_uint8(num_steps),
                                   self._pack_int8(turn),
                                   dur_lsb, dur_msb,
                                   self._pack_int8(step_length),
                                   side_c)


    def eyes(self, angle, move_time=100):
        '''
        Move the eyes to an angle
        Args:
            angle, int, degrees
            move_time, milliseconds
        '''
        return self.move_joint(8, angle, move_time)


    def kick(self, side='right', twist=0, move_time=2000):
        '''
        Kick with Marty's feet
        Args:
            side: 'left' or 'right', which foot to use
            twist: TODO
            move_time: how long this movement should last, in milliseconds
        '''
        side_c = self.SIDE_CODES[side]
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('kick', side_c,
                                   self._pack_int8(twist),
                                   dur_lsb, dur_msb)


    def arms(self, left_angle, right_angle, move_time):
        '''
        Move the arms to a position
        Args:
            left_angle: Position of the left arm
            right_angle: Position of the right arm
            move_time: how long this movement should last, in milliseconds
        '''
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('arms',
                                   self._pack_int8(right_angle),
                                   self._pack_int8(left_angle),
                                   dur_lsb, dur_msb)



    def celebrate(self, move_time=4000):
        '''
        Do a small celebration
        Args:
            move_time: how long this movement should last, in milliseconds
        '''
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('celebrate', dur_lsb, dur_msb)


    def circle_dance(self, side='right', move_time=1500):
        '''
        Boogy, Marty!
        '''
        side_c = self.SIDE_CODES[side]
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('circle_dance',
                                   side_c,
                                   dur_lsb, dur_msb)


    def sidestep(self, side, steps=1, step_length=100, move_time=2000):
        '''
        Take sidesteps
        Args:
            side: 'left' or 'right', direction to step in
            steps: number of steps to take
            step length: how broad the steps are
            move_time: how long this movement should last, in milliseconds
        '''
        side_c = self.SIDE_CODES[side]
        dur_lsb, dur_msb = self._pack_uint16(move_time)
        return self.client.execute('sidestep', side_c,
                                   self._pack_int8(steps),
                                   dur_lsb, dur_msb,
                                   self._pack_int8(step_length))


    def play_sound(self, freq_start, freq_end, duration):
        '''
        Play a tone
        Args:
            freq_start: starting frequency, Hz
            freq_end:   ending frequency, Hz
            duration:   milliseconds, maximum 5000
        '''
        f_start_lsb, f_start_msb = self._pack_uint16(freq_start)
        f_end_lsb, f_end_msb = self._pack_uint16(freq_end)
        dur_lsb, dur_msb = self._pack_uint16(duration)
        return self.client.execute('play_sound',
                                   f_start_lsb, f_start_msb,
                                   f_end_lsb, f_end_msb,
                                   dur_lsb, dur_msb)




    GPIO_PIN_MODES = {
        'digital in'  : '\x00',
        'analog in'   : '\x01',
        'digital out' : '\x02',
        #'servo'       : '\x03',
        #'pwm'         : '\x04',
    }


    def pinmode_gpio(self, gpio, mode):
        '''
        Configure a GPIO pin
        '''
        raise NotImplementedError()
        return self.client.execute('i2c_write', byte_array)


    def write_gpio(self, gpio, value):
        '''
        Write a value to a GPIO port
        '''
        raise NotImplementedError()
        return self.client.execute('gpio_write', byte_array)


    def digitalread_gpio(self, gpio):
        '''
        Returns:
            Returns High/Low state of a GPIO pin
        Args:
            GPIO pin number, >= 0 (non-negative)
        '''
        return bool(self.client.execute('gpio', self._pack_uint8(gpio)))


    def i2c_write(self, byte_array):
        '''
        Write a bytestream to the i2c port.
        The first byte should be the address, following from that
        the datagram folows standard i2c spec
        '''
        raise NotImplementedError()
        return self.client.execute('i2c_write', byte_array)


    def get_battery_voltage(self):
        '''
        Returns:
            The battery voltage reading as a float in Volts
        '''
        return self.client.execute('battery')


    ACCEL_AXES = {
        'x' : '\x00',
        'y' : '\x01',
        'z' : '\x02',
    }


    def get_accelerometer(self, axis):
        '''
        Args:
            axis: str 'x', 'y' or 'z'
        Returns:
            The most recently read x, y and z accelerations
        '''
        try:
            ax = self.ACCEL_AXES[axis]
        except KeyError:
            raise MartyCommandException("Axis must be one of {}, not '{}'"
                                        "".format(set(self.ACCEL_AXES.keys()), axis))
        return self.client.execute('accel', ax)


    def get_motor_current(self, motor_id):
        '''
        Args:
            motor_id, integer >= 0 (non-negative) selects which motor to query
        Returns:
            Instantaneous current sense reading from motor `motor_id`
        '''
        return self.client.execute('motorcurrent', int(motor_id))


    def enable_motors(self, enable=True, clear_queue=True):
        '''
        Toggle power to motors
        Args:
            enable: True/False toggle
            clear_queue: Default True, prevents unfinished but 'muted' motions
                         from jumping as soon as motors are enabled
        '''
        if clear_queue:
            self.stop('clear queue')
        if enable:
            return self.client.execute('enable_motors') and True
        else:
            return self.client.execute('disable_motors') and False


    def enable_safeties(self, enable=True):
        '''
        Tell the board to turn on 'normal' safeties
        '''
        return self.client.execute('enable_safeties')


    def fall_protection(self, enable=True):
        '''
        Toggle fall protections
        Args:
            enable: True/False toggle
        '''
        return self.client.execute('fall_protection', enable)


    def motor_protection(self, enable=True):
        '''
        Toggle motor current protections
        Args:
            enable: True/False toggle
        '''
        return self.client.execute('motor_protection', enable)


    def battery_protection(self, enable=True):
        '''
        Toggle low battery protections
        Args:
            enable: True/False toggle
        '''
        return self.client.execute('battery_protection', enable)


    def buzz_prevention(self, enable=True):
        '''
        Toggle motor buzz prevention
        Args:
            enable: True/False toggle
        '''
        return self.client.execute('buzz_prevention', enable)


    def lifelike_behaviour(self, enable=True):
        '''
        Tell the robot whether it can or can't move now and then in a lifelike way when idle.
        Args:
            enable: True/False toggle
        '''
        return self.client.execute('lifelike_behaviour', enable)


    def set_parameter(self):
        '''
        Return the board's firmware version
        '''
        raise NotImplementedError()
        return self.client.execute('set_param')


    def save_calibration(self):
        '''
        Set the current motor positions as the zero positions
        BE CAREFUL, this can cause unexpected movement or self-interference
        '''
        return self.client.execute('save_calibration')


    def clear_calibration(self):
        '''
        Tell the Robot to forget it's calibration
        BE CAREFUL, this can cause unexpected movement or self-interference
        '''
        return self.client.execute('clear_calibration')


    def ros_command(self, byte_array):
        '''
        Low level proxied access to the ROS Serial API between
        the modem and main controller
        '''
        return self.client.execute('ros_command', byte_array)


    def get_chatter(self):
        '''
        Return chatter topic data (variable length)
        '''
        return self.client.execute('chatter')


    def get_firmware_version(self):
        '''
        Ask the board to print the firmware version over chatter
        '''
        raise NotImplementedError()
        return self.client.execute('firmware_version')



    def _mute_serial(self):
        '''
        Mutes the internal serial line on Rick. Depends on platform and API
        NOTE: Once you've done this, the Robot will ignore you until you cycle power.
        '''
        return self.client.execute('mute_serial')
        
