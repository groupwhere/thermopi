#!/usr/bin/python
#Based off the tutorial by adafruit here:
# http://learn.adafruit.com/adafruits-raspberry-pi-lesson-11-ds18b20-temperature-sensing/software

import subprocess
import glob
import time
import ConfigParser

config = ConfigParser.ConfigParser()
config.read("config.txt")

def getIndoorTemp():
    subprocess.Popen('modprobe w1-gpio', shell=True)
    subprocess.Popen('modprobe w1-therm', shell=True)
    base_dir = '/sys/bus/w1/devices/'
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        f = open(device_file, 'r')
        lines = f.readlines()
        f.close()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        if SCALE == 'F':
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            return temp_f
        else:
            return temp_c

    return read_temp()
