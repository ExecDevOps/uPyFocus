from machine import Pin
from machine import PWM
from machine import Timer
import utime

class Stepper:
    """
    Handles  A4988 hardware driver for bipolar stepper motors
    """

    def __init__(self, motor_id, dir_pin, step_pin, enable_pin, freq=1000, full_steps=1910):
        self.step_pin = step_pin
        self.dir_pin = dir_pin
        self.enable_pin = enable_pin
        self.freq = freq
        self.full_steps = full_steps

        self.step_pin.init(Pin.OUT)
        self.dir_pin.init(Pin.OUT)
        self.enable_pin.init(Pin.OUT)
        self.enable_pin.on()       

        self.dir = 0
        self.steps = 0
        self.count = 0

        self.pwm = PWM(self.step_pin, freq=self.freq, duty=0)
        self.tim = Timer(motor_id)

        self.tim.init(period=1, mode=Timer.PERIODIC, callback=self.do_step)

        self.done = False

    def do_step(self, t):   # called by timer interrupt every (freq/1000)ms
        if self.count == 0:
            self.done = False
            self.pwm.duty(512)
        elif self.count >= self.steps:
            self.done = True
            self.pwm.duty(0)

        if self.count != -1:
            self.count = self.count + self.freq/1000

    def set_motion(self, steps):
        self.set_on()
        # set direction
        if steps > 0:
            self.dir = 1
            self.dir_pin.on()
            self.enable_pin.off()       
        elif steps<0:
            self.dir = -1
            self.dir_pin.off()
            self.enable_pin.off()       
        else:
            self.dir = 0
        # set steps
        self.count = 0
        self.steps = abs(steps)

    def set_on(self):
        self.enable_pin.on()

    def set_off(self):
        self.count = -1
        self.steps = 0
        self.pwm.duty(0)
        self.done = True
        self.enable_pin.off()

    def get_step(self):
        return self.count

    def get_status(self):
        if self.count == -1:
            return False
        elif self.count <= self.steps:
            return True
        else:
            return False


class Axis: 
    def __init__(self, axis, ina, max_current):
        self.axes = axis
        self.ina = ina
        self.margin = 100
        self.max_steps = 0
        self.max_current = max_current
        self.actual_position = 0
        self.calibrated = False

    def calibration(self):
        rotation = self.axes.full_steps * 2

        # detection homing
        self.axes.set_motion(rotation)

        while self.axes.get_status():            
            # avoid -> maximum recursion depth exceeded
            #current = self.ina.current()
            self.ina._handle_current_overflow()
            current = self.ina._current_register() * self.ina._current_lsb * 1000
            if current > self.max_current:
                self.axes.set_off()
        
        # detection maximum
        self.axes.set_motion(-rotation)
        
        while self.axes.get_status():
            # avoid -> maximum recursion depth exceeded
            #current = self.ina.current()
            self.ina._handle_current_overflow()
            current = self.ina._current_register() * self.ina._current_lsb * 1000
            if current > self.max_current:
                self.max_steps = self.axes.get_step()
                self.axes.set_off()
        
        self.axes.set_motion(self.margin)

        self.actual_position = self.max_steps - self.margin


        self.calibrated = True
        
        return self.max_steps

    def move(self, steps):
        if not self.calibrated:
            return False

        position = self.actual_position + steps

        if position > self.max_steps - self.margin:
            return False
        if position < self.margin:
            return False
        else:
            if self.axes.done:
                self.axes.set_motion(-steps)
                self.actual_position = position
                return True
            return False

    def move_max(self):
        position = self.max_steps - self.actual_position
        self.move(position)
    
    def move_min(self):
        position = self.actual_position
        self.move(-position)