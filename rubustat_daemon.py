#! /usr/bin/python

import sys
import subprocess
import os
import time
import datetime
import ConfigParser
import urllib2
import json
from daemon import Daemon
from getIndoorTemp import getIndoorTemp
from threading import Timer
from operator import itemgetter

import sqlite3
from schedule import schedule

#set working directory to where "rubustat_daemon.py" is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

#read values from the config file
config = ConfigParser.ConfigParser()
config.read("config.txt")
DEBUG = int(config.get('main','DEBUG'))
GPIOE = int(config.get('main','GPIOE'))
active_hysteresis = float(config.get('main','active_hysteresis'))
inactive_hysteresis = float(config.get('main','inactive_hysteresis'))
SCALE = config.get('main','SCALE')
ZIP = config.get('weather','ZIP')
STATE = config.get('weather','STATE')
WUNDERGROUND = config.get('weather','WUNDERGROUND')
HEATER_PIN = int(config.get('main','HEATER_PIN'))
AC_PIN = int(config.get('main','AC_PIN'))
FAN_PIN = int(config.get('main','FAN_PIN'))
# Heat pump
OB_PIN = int(config.get('main','OB_PIN'))
OB_POS = int(config.get('main','OB_POS'))
# Type 0 == Normal, 1 == Heat pump
AC_TYPE = int(config.get('main','AC_TYPE'))
PIN_OFF = int(config.get('main','PIN_OFF'))
PIN_ON  = int(config.get('main','PIN_ON'))
# When does the emergency heat get turned on?
emergency_temp = float(config.get('main','emergency_temp'))

weatherEnabled = config.getboolean('weather','enabled')

scheduleEnabled = config.getboolean('schedule','enabled')
# Adafruit DHT11 and others
sensor_type = config.get('main','sensor_type')
sensor_pin  = int(config.get('main','sensor_pin'))

if GPIOE == 1:
    import RPi.GPIO as GPIO

if sensor_type == 'DHT_11':
    import Adafruit_DHT

#mail config
mailEnabled = config.getboolean('mail', 'enabled')
if mailEnabled == True:
    import smtplib

    config.read("mailconf.txt")
    SMTP_SERVER = config.get('mailconf','SMTP_SERVER')
    SMTP_PORT = int(config.get('mailconf','SMTP_PORT'))
    username = config.get('mailconf','username')
    password = config.get('mailconf','password')
    sender = config.get('mailconf','sender')
    recipient = config.get('mailconf','recipient')
    subject = config.get('mailconf','subject')
    body = config.get('mailconf','body')
    errorThreshold = float(config.get('mail','errorThreshold'))

class rubustatDaemon(Daemon):
    dschedule = schedule()
    dschedule.read_schedule()

    def configureGPIO(self):
        if GPIOE == 1:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            if DEBUG >= 1:
                sys.stderr.write("Setting up GPIO.\n")
                log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                log.write("Setting up GPIO at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                log.close()
    
            GPIO.setup(HEATER_PIN, GPIO.OUT, initial=PIN_OFF)
            GPIO.setup(OB_PIN, GPIO.OUT, initial=PIN_OFF)
            GPIO.setup(AC_PIN, GPIO.OUT, initial=PIN_OFF)
            GPIO.setup(FAN_PIN, GPIO.OUT, initial=PIN_OFF)
    
            subprocess.Popen("echo " + str(HEATER_PIN) + " > /sys/class/gpio/export", shell=True)
            subprocess.Popen("echo " + str(OB_PIN) + " > /sys/class/gpio/export", shell=True)
            subprocess.Popen("echo " + str(AC_PIN) + " > /sys/class/gpio/export", shell=True)
            subprocess.Popen("echo " + str(FAN_PIN) + " > /sys/class/gpio/export", shell=True)

    def getHVACState(self):
        if GPIOE == 1:
            obStatus   = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(OB_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
            heatStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(HEATER_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
            coolStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(AC_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
            fanStatus  = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(FAN_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
    
            if AC_TYPE == 0:
                # Standard AC
                if heatStatus == PIN_ON and fanStatus == PIN_ON:
                    #heating
                    return 1
                elif coolStatus == PIN_ON and fanStatus == PIN_ON:
                    #cooling
                    return -1
                elif heatStatus == PIN_OFF and coolStatus == PIN_OFF and fanStatus == PIN_OFF:
                    #idle
                    return 0
                else:
                    #broken
                    return 2
            else:
                # Heat pump
                if heatStatus == PIN_ON and fanStatus == PIN_ON and coolStatus == PIN_OFF and obStatus == PIN_OFF:
                    #emergency heat
                    return -2
                elif heatStatus == PIN_OFF and fanStatus == PIN_ON and coolStatus == PIN_ON and obStatus == PIN_ON:
                    #heating
                    return 1
                elif heatStatus == PIN_OFF and coolStatus == PIN_ON and fanStatus == PIN_ON and obStatus == PIN_OFF:
                    #cooling
                    return -1
                elif heatStatus == PIN_OFF and coolStatus == PIN_OFF and fanStatus == PIN_OFF and obStatus == PIN_OFF:
                    #idle
                    return 0
                else:
                    #broken
                    return 2
        else:
            return 0

    def cool(self):
        if DEBUG >= 1:
            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("Setting unit to cool.\n")
            log.close()

        if GPIOE == 1:
            if AC_TYPE == 0:
                GPIO.output(HEATER_PIN, PIN_OFF)
                GPIO.output(AC_PIN, PIN_ON)
                GPIO.output(FAN_PIN, PIN_ON)
                return -1
            else:
                GPIO.output(HEATER_PIN, PIN_OFF)
                GPIO.output(OB_PIN, PIN_OFF)
                GPIO.output(AC_PIN, PIN_ON)
                GPIO.output(FAN_PIN, PIN_ON)
                return -1
        else:
            return -1

    def heat(self):
        if DEBUG >= 1:
            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("Setting unit to heat.\n")
            log.close()

        if GPIOE == 1:
            if AC_TYPE == 0:
                GPIO.output(HEATER_PIN, PIN_ON)
                GPIO.output(AC_PIN, PIN_OFF)
                GPIO.output(FAN_PIN, PIN_ON)
                return 1
            else:
                GPIO.output(HEATER_PIN, PIN_OFF)
                GPIO.output(OB_PIN, PIN_ON)
                GPIO.output(AC_PIN, PIN_ON)
                GPIO.output(FAN_PIN, PIN_ON)
                return 1
        else:
            return -1

    def eheat(self):
        if DEBUG >= 1:
            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("Setting unit to EMERGENCY heat.\n")
            log.close()

        if GPIOE == 1:
            if AC_TYPE == 0:
                GPIO.output(HEATER_PIN, PIN_ON)
                GPIO.output(AC_PIN, PIN_OFF)
                GPIO.output(FAN_PIN, PIN_ON)
                return 1
            else:
                GPIO.output(HEATER_PIN, PIN_ON)
                GPIO.output(OB_PIN, PIN_OFF)
                GPIO.output(AC_PIN, PIN_OFF)
                GPIO.output(FAN_PIN, PIN_ON)
                return 1
        else:
            return -1
    def fan_to_idle(self):
        #to blow the rest of the heated / cooled air out of the system
        if DEBUG >= 1:
            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("Setting unit to idle with fan.\n")
            log.close()

        if GPIOE == 1:
            GPIO.output(HEATER_PIN, PIN_OFF)
            GPIO.output(AC_PIN, PIN_OFF)
            GPIO.output(OB_PIN, PIN_OFF)
            GPIO.output(FAN_PIN, PIN_ON)

    def idle(self):
        if DEBUG >= 1:
            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("Setting unit to idle (off) for 5 minutes.\n")
            log.close()

        if GPIOE == 1:
            GPIO.output(HEATER_PIN, PIN_OFF)
            GPIO.output(OB_PIN, PIN_OFF)
            GPIO.output(AC_PIN, PIN_OFF)
            GPIO.output(FAN_PIN, PIN_OFF)
            #delay to preserve compressor - not while testing
            #time.sleep(300)
        return 0

    if mailEnabled == True:
        def sendErrorMail(self):
            headers = ["From: " + sender,
                    "Subject: " + subject,
                    "To: " + recipient,
                    "MIME-Version: 1.0",
                    "Content-Type: text/html"]
            headers = "\r\n".join(headers)
            session = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            session.ehlo()
            #you may need to comment this line out if you're a crazy person
            #and use non-tls SMTP servers
            #session.starttls()
            session.ehlo
            session.login(username, password)
            session.sendmail(sender, recipient, headers + "\r\n\r\n" + body)
            session.quit()

    def getWeather(self):
        url = 'http://api.wunderground.com/api/' + str(WUNDERGROUND) + '/geolookup/conditions/q/' + STATE + '/' + ZIP + '.json'
#        if DEBUG >= 1:
#            print "Fetching " + url + "\n"
        f = urllib2.urlopen(url)
        json_string = f.read()
        parsed_json = json.loads(json_string)
        city = parsed_json['location']['city']
        state = parsed_json['location']['state']
        weather = parsed_json['current_observation']['weather']
        temperature_string = parsed_json['current_observation']['temperature_string']
        feelslike_string = parsed_json['current_observation']['feelslike_string']
        weatherstring = 'Weather in ' + city + ', ' + state + ': ' + weather.lower() + ".\n" + 'The temperature is ' + temperature_string + ' and it feels like ' + feelslike_string + '.'
        f.close()

        wconn = sqlite3.connect("status.db",timeout=10)
        c = wconn.cursor()
        now = datetime.datetime.now()
        c.execute('INSERT INTO weather VALUES(?, ?)', (now, weatherstring))
        wconn.commit()
        wconn.close()

        return weatherstring

    def updateTemp(self):
#        if DEBUG >= 1:
#        print "Called updateTemp\n"

        if sensor_type == 'DHT_11':
            sensor = 11
            humidity, temperature = Adafruit_DHT.read_retry(sensor, sensor_pin)
            if temperature:
                if SCALE == 'F':
                    indoorTemp = float(temperature * 9/5.0 + 32)
                else:
                    indoorTemp = float(temperature)
            else:
                indoorTemp = 0
            if not humidity:
                humidity = 0
        else:
            #self.humidity = ''
            humidity = 0
            indoorTemp = float(getIndoorTemp())

        sconn = sqlite3.connect("status.db",timeout=10)
        c = sconn.cursor()
        found = False
        cursor = c.execute("SELECT COUNT(datetime) FROM readings")
        for row in cursor:
            if row[0] > 0:
                found = True

        now = datetime.datetime.now()
        if found == True:
            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("UPDATE readings in DB to: " + str(indoorTemp) + ", " + str(humidity) + "\n")
            log.close
            c.execute("UPDATE readings SET datetime=?, indoorTemp=?, humidity=?", (now, indoorTemp, humidity))
        else:
            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("INSERT readings\n")
            log.close
            c.execute("INSERT INTO readings VALUES (?, ?, ?)", (now, indoorTemp, humidity))

        sconn.commit()
        sconn.close()

        return str(humidity),str(round(indoorTemp,1))

    def run(self):
        lastLog = datetime.datetime.now()
        lastMail = datetime.datetime.now()
        self.configureGPIO()

        (humidity,indoorTemp) = self.updateTemp()

        if weatherEnabled == True:
            Timer(30, self.getWeather, ()).start()

        while True:
            #change cwd to wherever rubustat_daemon is
            abspath = os.path.abspath(__file__)
            dname = os.path.dirname(abspath)
            os.chdir(dname)

            (humidity,indoorTemp) = self.updateTemp()
            humidity = float(humidity)
            indoorTemp = float(indoorTemp)

            hvacState = int(self.getHVACState())

            # Fetch the most recent status just in case there is more than one.
            targetTemp = 0
            mode = ''
            sconn = sqlite3.connect("status.db",timeout=10)
            cursor = sconn.execute('SELECT targetTemp, mode FROM status ORDER BY datetime DESC LIMIT 1')

            for row in cursor:
                targetTemp = float(row[0])
                mode = str(row[1])

            sconn.close()

            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
            log.write("Read targetTemp and mode from DB: '" + str(targetTemp) + "', '" + mode + "'\n")
            log.close

            now = datetime.datetime.now()
            logElapsed = now - lastLog
            mailElapsed = now - lastMail

            # Verify schedule is enabled but also that the unit was not set manually to 'off'.  Off means off.
            if scheduleEnabled == True:
                now = datetime.datetime.now()
                # Set the current schedule
                if DEBUG >= 1:
                    print "Checking schedule"
                #if self.dschedule.holding == False:
                self.dschedule.read_schedule()
                self.dschedule.set_current()
                # (re)set the mode based on the schedule, if any
                #self.dschedule.check_schedule()
                turnon = False
                low = ''
                high = ''
                if mode != 'off' and self.dschedule.active == True:
                    if len(self.dschedule.current):
                        turnon = True
                        # Compare indoorTemp and schedule temp settings
                        low  = itemgetter(5)(self.dschedule.current)
                        high = itemgetter(6)(self.dschedule.current)
                        if indoorTemp < low: #and mode != 'off':
                            mode = 'heat'
                            targetTemp = low
                        elif indoorTemp > high: #and mode != 'off':
                            mode = 'cool'
                            targetTemp = high

                if DEBUG >= 1:
                    log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                    log.write("Schedule: active? " + str(self.dschedule.active) + ".\n")
                    log.close()

                scconn = sqlite3.connect("status.db",timeout=10)
                sc = scconn.cursor()
                # This is the schedule status not the schedule.db list of schedules.  Single line of data like the status table
                if self.dschedule.holding == False:
                    sc.execute("DELETE FROM schedule")
                    if len(self.dschedule.current):
                        sc.execute("INSERT INTO schedule (datetime,name,active) VALUES (?,?,?)", (now,itemgetter(0)(self.dschedule.current), self.dschedule.active))
                    sc.execute("DELETE FROM status")
                    sc.execute("INSERT INTO status (datetime,targetTemp,mode) VALUES (?,?,?)", (now, targetTemp, mode))
                    scconn.commit()
                    scconn.close()

                if DEBUG >= 1 and self.dschedule.current:# and turnon == True:
                    log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                    log.write("Schedule: Set to " + str(self.dschedule.current) + "\n")
                    log.write("Schedule: New mode set to " + mode + "\n")
                    log.write("Schedule: New targetTemp set to " + str(targetTemp) + "\n")
                    log.write("Schedule: LOW = " + str(low) + ", HIGH = " + str(high) + "\n")
                    log.write("Schedule: Active? " + str(self.dschedule.active) + "\n")
                    log.close()

            ### check if we need to send error mail
            #cooling
            #it's 78, we want it to be 72, and the error threshold is 5 = this triggers
            if mailEnabled == True and (mailElapsed > datetime.timedelta(minutes=20)) and (float(indoorTemp) - float(targetTemp)) > errorThreshold:
                self.sendErrorMail()
                lastMail = datetime.datetime.now()
                if DEBUG >= 1:
                    log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                    log.write("MAIL: Sent mail to " + recipient + " at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                    log.close()

            #heat
            #it's 72, we want it to be 78, and the error threshold is 5 = this triggers
            if mailEnabled == True and (mailElapsed > datetime.timedelta(minutes=20)) and (float(targetTemp) - float(indoorTemp)) > errorThreshold:
                self.sendErrorMail()
                lastMail = datetime.datetime.now()
                if DEBUG >= 1:
                    log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                    log.write("MAIL: Sent mail to " + recipient + " at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                    log.close()

            #logging actual temp and indoor temp to sqlite database.
            #you can do fun things with this data, like make charts!
            if logElapsed > datetime.timedelta(minutes=6):
                self.conn = sqlite3.connect("temperatureLogs.db",timeout=10)
                self.c = self.conn.cursor()

                self.c.execute('INSERT INTO logging VALUES(?, ?, ?)', (now, indoorTemp, targetTemp))
                self.conn.commit()
                self.conn.close()
                lastLog = datetime.datetime.now()

            # heater mode
            if mode == "heat":
                if hvacState == 0: #idle
                    if float(indoorTemp) < float(targetTemp) - inactive_hysteresis:
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to heat at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        # switch to heat
                        hvacState = self.heat()
                elif hvacState == 1: #heating
                    if float(indoorTemp) > float(targetTemp) + active_hysteresis:
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to fan_to_idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        self.fan_to_idle()
                        time.sleep(30)
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        # switch to idle
                        hvacState = self.idle()
                    elif float(indoorTemp) < float(emergency_temp) + active_hysteresis:
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to eheat at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        # switch to eheat
                        hvacState = self.eheat()
                elif hvacState == -2: # emergency heat running but already warm enough
                    if float(indoorTemp) > float(emergency_temp) + active_hysteresis:
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to heat from eheat at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        hvacState = self.heat()
                elif hvacState == -1: # it's cold out, why is the AC running?
                    if DEBUG >= 1:
                        log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                        log.write("STATE: Switching to idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                        log.close()
                    hvacState = self.idle()
            # ac mode
            elif mode == "cool":
                if hvacState == 0: #idle
                    if float(indoorTemp) > float(targetTemp) + inactive_hysteresis:
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to cool at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        hvacState = self.cool()
                elif hvacState == -1: #cooling
                    if float(indoorTemp) < float(targetTemp) - active_hysteresis:
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to fan_to_idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        self.fan_to_idle()
                        time.sleep(30)
                        if DEBUG >= 1:
                            log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                            log.write("STATE: Switching to idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                            log.close()
                        hvacState = self.idle()
                elif hvacState == 1: # it's hot out, why is the heater on?
                    if DEBUG >= 1:
                        log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                        log.write("STATE: Switching to fan_to_idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                        log.close()
                    hvacState = self.idle()
                elif hvacState == -2: # it's hot out, why is the emergency heater on?
                    if DEBUG >= 1:
                        log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                        log.write("STATE: Switching to fan_to_idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                        log.close()
                    hvacState = self.idle()
            elif mode == "off":
                if hvacState == -1: #cooling
                    if DEBUG >= 1:
                        log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                        log.write("STATE: Switching to fan_to_idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                        log.close()
                    self.fan_to_idle()
                    time.sleep(30)
                elif hvacState == 1: # it's hot out, why is the heater on?
                    if DEBUG >= 1:
                        log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                        log.write("STATE: Switching to fan_to_idle at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")
                        log.close()
                    hvacState = self.idle()
                else: # OFF
                    hvacState = self.idle()
            else:
                print "It broke."

            #loggin'stuff
            if DEBUG >= 1:
                if PIN_ON == 0:
                    obStatus   = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(OB_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                    heatStatus = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(HEATER_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                    coolStatus = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(AC_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                    fanStatus  = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(FAN_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                else:
                    obStatus   = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(OB_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                    heatStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(HEATER_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                    coolStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(AC_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                    fanStatus  = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(FAN_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
                log = open("logs/debug_" + datetime.datetime.now().strftime('%Y%m%d') + ".log", "a")
                log.write("Report at " + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + ":\n")
                log.write("hvacState = " + str(hvacState)+ "\n")
                log.write("indoorTemp = " + str(indoorTemp)+ "\n")
                log.write("targetTemp = " + str(targetTemp)+ "\n")
                log.write("heatStatus = " + str(heatStatus) + "\n")
                log.write("obStatus = " + str(obStatus)+ "\n")
                log.write("coolStatus = " + str(coolStatus)+ "\n")
                log.write("fanStatus = " + str(fanStatus)+ "\n")
                log.close()

            time.sleep(5)

if __name__ == "__main__":
    daemon = rubustatDaemon('rubustatDaemon.pid')

    #Setting up logs
    if not os.path.exists("logs"):
        subprocess.Popen("mkdir logs", shell=True)

    conn = sqlite3.connect("temperatureLogs.db",timeout=10)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS logging (datetime TIMESTAMP, actualTemp FLOAT, targetTemp INT)')
    conn.close()

    sconn = sqlite3.connect("status.db",timeout=10)
    cs = sconn.cursor()
    cs.execute('CREATE TABLE IF NOT EXISTS weather (datetime TIMESTAMP, weather TEXT)')
    cs.execute('CREATE TABLE IF NOT EXISTS status (datetime TIMESTAMP, targetTemp INT, mode TEXT)')
    cs.execute('CREATE TABLE IF NOT EXISTS readings (datetime TIMESTAMP, indoorTemp TEXT, humidity TEXT)')
    cs.execute('CREATE TABLE IF NOT EXISTS readings (datetime TIMESTAMP, indoorTemp TEXT, humidity TEXT)')
    cs.execute('CREATE TABLE IF NOT EXISTS schedule (datetime TIMESTAMP, name TEXT, active BOOL)')
    sconn.close()

    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            #stop all HVAC activity when daemon stops
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(HEATER_PIN, GPIO.OUT, initial=PIN_OFF)
            GPIO.setup(OB_PIN, GPIO.OUT, initial=PIN_OFF)
            GPIO.setup(AC_PIN, GPIO.OUT, initial=PIN_OFF)
            GPIO.setup(FAN_PIN, GPIO.OUT, initial=PIN_OFF)
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
            sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)

