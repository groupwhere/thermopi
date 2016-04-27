#!/usr/bin/python
import os
import subprocess
import re
import time
import datetime
import ConfigParser
import logging
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
        abort, render_template, flash, jsonify

app = Flask(__name__)
#hard to be secret in open source... >.>
app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

config = ConfigParser.ConfigParser()
config.read("config.txt")
DEBUG = int(config.get('main','DEBUG'))
HEATER_PIN = int(config.get('main','HEATER_PIN'))
AC_PIN = int(config.get('main','AC_PIN'))
OB_PIN = int(config.get('main','OB_PIN'))
FAN_PIN = int(config.get('main','FAN_PIN'))
SCALE = config.get('main','SCALE')
weatherEnabled = config.getboolean('weather','enabled')
scheduleEnabled = config.getboolean('schedule','enabled')

#start the daemon in the background
subprocess.Popen("/usr/bin/python rubustat_daemon.py start", shell=True)

if weatherEnabled == True:
    def getWeather():
        conn = sqlite3.connect("status.db")
        found = False
        cursor = conn.execute("SELECT COUNT(datetime) FROM weather")
        for row in cursor:
            if row[0] > 0:
                found = True

        if found == True:
            cursor = conn.execute('SELECT weather from weather ORDER BY datetime DESC LIMIT 1')
            for row in cursor:
                weatherstring = row[0]
        else:
            weatherstring = 'Weather information is currently unavailable.'

        conn.close()

        return weatherstring

# Schedule display functions
if scheduleEnabled == True:
    from schedule import schedule
    webschedule = schedule()

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
        if bool(scheduleactive) == True:
            schedString = "<p id=\"schedOn\"> [" + schedulename + "] ACTIVE</p>"
        else:
            schedString = "<p id=\"schedOn\"> [" + schedulename + "] inactive</p>"
        return schedString

    def get_sched_detail(name):
        # Gets the current schedule for display
        global webschedule
        days = ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
        webschedule.read_schedule()
        current = webschedule.set_current()

        #(u'Home', 3, u'04:30:00', 3, u'06:30:00', 67.0, 74.0)
        startday = days[itemgetter(1)(current)]
        start    = itemgetter(2)(current)
        endday   = days[itemgetter(3)(current)]
        end      = itemgetter(4)(current)
        low      = str(itemgetter(5)(current))
        high     = str(itemgetter(6)(current))

        return "<p id=\"schedDetail\">[" + name + "] starts " + startday + " at " + start + " and ends " + endday + " at " + end + " with min/max temp of " + low + "/" + high + ".</p>"

    def disSched():
        # Disable current schedule
        if scheddisF.get() == 'enable':
            scheddisF.set('disable')
            newmode.set('cool')
        else:
            scheddisF.set('enable')
            newmode.set('off')
        setStat()

def getWhatsOn():
    obStatus   = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(OB_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
    heatStatus = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(HEATER_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
    coolStatus = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(AC_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
    fanStatus  = not int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(FAN_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())

    obString   = "<p id=\"heat\"> heat off </p>"
    heatString = "<p id=\"heat\"> heat off </p>"
    coolString = "<p id=\"cool\"> cool off </p>"
    fanString  = "<p id=\"fan\"> fan off </p>"
    if heatStatus == 1:
        heatString = "<p id=\"heatOn\"> ON EMERGENCY </p>"
    elif coolStatus == 1 and obStatus == 1:
        heatString = "<p id=\"heatOn\"> HEAT ON </p>"
    if coolStatus == 1 and obStatus == 0:
        coolString = "<p id=\"coolOn\"> COOL ON </p>"
    if fanStatus == 1:
        fanString = "<p id=\"fanOn\"> FAN ON </p>"

    return heatString + coolString + fanString

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
    mode = ''
    targetTemp = 0
    conn = sqlite3.connect("status.db")
    found = False

    cursor = conn.execute("SELECT COUNT(datetime) FROM status")
    for row in cursor:
        if row[0] > 0:
            found = True

    if found == True:
        cursor = conn.execute('SELECT targetTemp, mode FROM status ORDER BY datetime DESC LIMIT 1')

        for row in cursor:
            targetTemp = int(row[0])
            mode = row[1]
    else:
        if SCALE == 'F':
            targetTemp = 75
        else:
            targetTemp = 32
        mode = 'off'

    conn.close()
    #whatsOn.set(getWhatsOn())

    #find out what mode the system is in, and set the switch accordingly
    #the switch is in the "cool" position when the checkbox is checked

    daemonStatus=getDaemonStatus()
    return mode,targetTemp

@app.route('/')
def my_form():
    (mode, targetTemp) = getStat()
 
    weatherString = ""
    if weatherEnabled == True:
        try:
            weatherString = getWeather()
        except:
            weatherString = "Couldn't get remote weather info! <br><br>"

    whatsOn = getWhatsOn()

    if scheduleEnabled == True:
        activeSchedule = getSched()
    else:
        activeSchedule = ''

    #find out what mode the system is in, and set the switch accordingly
    #the switch is in the "cool" position when the checkbox is checked

    daemonStatus = getDaemonStatus()

    if mode == "heat":
        checked = ""
    elif mode == "cool":
        checked = "checked=\"checked\""
    else:
        checked = "Something broke"

    #browser = request.user_agent.browser
    #browser = request.user_agent.string
    #logging.info(browser)

    #if browser == 'epiphany':
    #if 'epiphany' in browser:
    return render_template(
        "tform.html",
        targetTemp = targetTemp,
        weatherString = weatherString,
        checked = checked,
        daemonStatus = daemonStatus,
        whatsOn = whatsOn,
        activeSched = activeSchedule
    )
#    else:
#        return render_template("form.html", targetTemp = targetTemp, \
#                                weatherString = weatherString, \
#                                checked = checked, \
#                                daemonStatus = daemonStatus, \
#                                whatsOn = whatsOn)

@app.route("/", methods=['POST'])
def my_form_post():
    text = request.form['target']
    mode = "heat"
    #default mode to heat 
    #cool if the checkbox is returned, it is checked
    #and cool mode has been selected

    if 'onoffswitch' in request.form:
        mode = "cool"
    newTargetTemp = text.upper()
    match = re.search(r'^\d{2}$',newTargetTemp)
    if match:
        conn = sqlite3.connect("status.db")
        found = False
        c = conn.cursor()
        now = datetime.datetime.now()
        cursor = c.execute("SELECT COUNT(datetime) FROM status")
        for row in cursor:
            found = True

        if found == True:
            c.execute("UPDATE status SET datetime=?, targetTemp=?, mode=?", (now, newTargetTemp, mode))
        else:
            c.execute("INSERT INTO status VALUES ('?', ?, '?')", (now, newTargetTemp, mode))

        conn.commit()
        conn.close()

        if DEBUG == 1:
            flash("New temperature of " + newTargetTemp + " set!")

        return redirect(url_for('my_form'))
    else:
        if DEBUG == 1:
            flash("That is not a two digit number! Try again!")
            return redirect(url_for('my_form'))

#the flask views for the incredible and probably
#not at all standards compliant live data

@app.route('/_liveTemp', methods= ['GET'])
def updateTemp():
    conn = sqlite3.connect("status.db")
    found = False
    cursor = conn.execute("SELECT COUNT(datetime) FROM readings")
    for row in cursor:
        if row[0] > 0:
            found = True

    if found == True:
        cursor = conn.execute('SELECT indoorTemp, humidity FROM readings ORDER BY datetime DESC LIMIT 1')

        for row in cursor:
            indoorTemp = float(row[0])
            humidity = row[1]

    conn.close()

    return str(round(indoorTemp,1))
    #return str(humidity),str(round(indoorTemp,1))

@app.route('/_liveWhatsOn', methods= ['GET'])
def updateWhatsOn():

    return getWhatsOn()

@app.route('/_liveSched', methods= ['GET'])
def updateSched():

    return getSched()

@app.route('/_liveSchedDetail', methods= ['GET'])
def updateSchedDetail():

    return get_sched()

@app.route('/_liveDaemonStatus', methods= ['GET'])
def updateDaemonStatus():

    return getDaemonStatus()

if __name__ == "__main__":
    logging.basicConfig(filename='logs/access.log',level=logging.DEBUG)
    app.run("0.0.0.0", port=80)
