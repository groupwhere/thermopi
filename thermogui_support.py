#! /usr/bin/env python
#
# Support file for thermogui which handles all non-GUI functions
#  including config read, etc.
#
import sys
import os
import subprocess
import re
import time
import datetime
import ConfigParser
import logging
import sqlite3
from operator import itemgetter
from functools import partial
from getIndoorTemp import getIndoorTemp

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

config = ConfigParser.ConfigParser()
config.read("config.txt")
DEBUG = int(config.get('main','DEBUG'))
ZIP = config.get('weather','ZIP')
STATE = config.get('weather','STATE')
GPIOE = int(config.get('main','GPIOE'))
HEATER_PIN = int(config.get('main','HEATER_PIN'))
AC_PIN = int(config.get('main','AC_PIN'))
OB_PIN = int(config.get('main','OB_PIN'))
FAN_PIN = int(config.get('main','FAN_PIN'))
# Type 0 == Normal, 1 == Heat pump
AC_TYPE = int(config.get('main','AC_TYPE'))
PIN_OFF = int(config.get('main','PIN_OFF'))
PIN_ON  = int(config.get('main','PIN_ON'))
weatherEnabled = config.getboolean('weather','enabled')
scheduleEnabled = config.getboolean('schedule','enabled')

# Adafruit DHT11 and others
#sensor_type = config.get('main','sensor_type')
#sensor_pin  = int(config.get('main','sensor_pin'))

#start the daemon in the background
subprocess.Popen("/usr/bin/python rubustat_daemon.py start", shell=True)

humidity = ''
indoorTemp = ''
targetTemp = ''
daemonStatus = ''
mode = ''
schedulename = ''
scheduleactive = 0

if weatherEnabled == True:
    def getWeather():
        gconn = sqlite3.connect("status.db",timeout=10)
        found = False
        cursor = gconn.execute("SELECT COUNT(datetime) FROM weather")
        for row in cursor:
            if row[0] > 0:
                found = True

        if found == True:
            cursor = gconn.execute('SELECT weather from weather ORDER BY datetime DESC LIMIT 1')
            for row in cursor:
                weatherstring =  row[0]
        else:
            weatherstring = 'Weather information is currently unavailable.'

        gconn.close()

        return weatherstring

if scheduleEnabled == True:
    from schedule import schedule
    guischedule = schedule()
    def getSched():
        # Get the active schedule, if any
        gconn = sqlite3.connect("status.db",10)
        found = False
        # daemon status.db schedule, not the schedule class db
        cursor = gconn.execute("SELECT COUNT(datetime) FROM schedule")
        schedulename = ''
        scheduleactive = 0
        for row in cursor:
            if row[0] > 0:
                found = True

        if found == True:
            cursor = gconn.execute('SELECT name, active FROM schedule ORDER BY datetime DESC LIMIT 1')

            for row in cursor:
                schedulename = row[0]
                scheduleactive = row[1]
        gconn.close()

        #print "Schedule " + schedulename + " is " + str(scheduleactive)
        return str(schedulename),bool(scheduleactive)

    def setSched(name):
        now = datetime.datetime.now()
        gconn = sqlite3.connect("status.db",10)
        g = gconn.cursor()
        g.execute('DELETE FROM schedule')
        gconn.commit()
        g.execute('INSERT INTO schedule VALUES(?,?,?)', (now,name,1))
        gconn.commit()
        gconn.close()

        if DEBUG > 0:
            print "SCHEDULE OVERRIDE SET TO " + name

    def get_sched(name):
        # Gets the current schedule for display
        global guischedule
        days = ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
        guischedule.read_schedule()
        current = guischedule.set_current()

        #(u'Home', 3, u'04:30:00', 3, u'06:30:00', 67.0, 74.0)
        if len(current) > 1:
            startday = days[itemgetter(1)(current)]
            start    = itemgetter(2)(current)
            endday   = days[itemgetter(3)(current)]
            end      = itemgetter(4)(current)
            low      = str(itemgetter(5)(current))
            high     = str(itemgetter(6)(current))

            return "starts " + startday + " at " + start + " and ends " + endday + " at " + end + " with min/max temp of " + low + "/" + high + "."

        if guischedule.holding == True:
            return ""
        else:
            return "No active schedule."

# Main program functions
def getWhatsOn():
    if DEBUG > 0:
        print "Called getWhatsOn\n"
    if GPIOE == False:
        print "NO GPIO"
        return (0,0,0,0)
    if PIN_ON == 1:
        obStatus   = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(OB_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
        heatStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(HEATER_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
        coolStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(AC_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
        fanStatus  = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(FAN_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
    else:
        obStatus   = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(OB_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
        heatStatus = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(HEATER_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
        coolStatus = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(AC_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
        fanStatus  = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(FAN_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())

    return (obStatus,heatStatus,coolStatus,fanStatus)

def getDaemonStatus():
    try:
        with open('rubustatDaemon.pid'):
            pid = int(subprocess.Popen("cat rubustatDaemon.pid", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
            try:
                os.kill(pid, 0)
                return "<p id=\"daemonRunning\"> Daemon is running. </p>"
            except OSError:
                return "<p id=\"daemonNotRunning\"> DAEMON IS NOT RUNNING. </p>"
    except IOError:
        return "<p id=\"daemonNotRunning\"> DAEMON IS NOT RUNNING. </p>"

def getStat():
    if DEBUG > 0:
        print "Called getStat\n"

    mode = ''
    targetTemp = 0
    gconn = sqlite3.connect("status.db",timeout=10)
    found = False

    cursor = gconn.execute("SELECT COUNT(datetime) FROM status")
    for row in cursor:
        if row[0] > 0:
            found = True

    if found == True:
        cursor = gconn.execute('SELECT targetTemp, mode FROM status ORDER BY datetime DESC LIMIT 1')

        for row in cursor:
            targetTemp = int(row[0])
            mode = row[1]
    else:
        targetTemp = 75
        mode = 'off'

    gconn.close()
    #whatsOn.set(getWhatsOn())

    #find out what mode the system is in, and set the switch accordingly
    #the switch is in the "cool" position when the checkbox is checked

    daemonStatus=getDaemonStatus()
    return mode,targetTemp

def setStat(mode,target):
    #    match = re.search(r'^\d{2,4}$',target)
    if DEBUG > 0:
        print "Setting new mode, temp to: " + mode + ', ' + target

    gconn = sqlite3.connect("status.db",timeout=10)
    c = gconn.cursor()
    now = datetime.datetime.now()

    c.execute("DELETE FROM status")
    c.execute("INSERT INTO status (datetime,targetTemp,mode) VALUES (?,?,?)", (now, target, mode))
    gconn.commit()
    gconn.close()

    if DEBUG > 0:
        print("New temperature of " + target + " set!")

    (mode,target) = getStat()
    return (mode,target)

def updateTemp():
    global humidity, indoorTemp
    if DEBUG > 0:
        print "Called updateTemp\n"

    gconn = sqlite3.connect("status.db",timeout=10)
    found = False
    cursor = gconn.execute("SELECT COUNT(datetime) FROM readings")
    for row in cursor:
        if row[0] > 0:
            found = True

    if found == True:
        cursor = gconn.execute('SELECT indoorTemp, humidity FROM readings ORDER BY datetime DESC LIMIT 1')

        for row in cursor:
            indoorTemp = float(row[0])
            humidity = row[1]

    else:
        humidity = ''
        indoorTemp = 0

    gconn.close()

    return str(humidity),str(round(indoorTemp,1))

def updateWhatsOn():
    return getWhatsOn()

def updateDaemonStatus():
    return getDaemonStatus()

