#!/usr/bin/python
# TkInter GUI for Rubustat
import os
import subprocess
import re
import time
import datetime
import ConfigParser
import logging
import sqlite3

# GUI Bits
from Tkinter import *
import tkFont

from threading import Timer

# Thermo sensors
from getIndoorTemp import getIndoorTemp
import Adafruit_DHT

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

config = ConfigParser.ConfigParser()
config.read("config.txt")
DEBUG = int(config.get('main','DEBUG'))
ZIP = config.get('weather','ZIP')
STATE = config.get('weather','STATE')
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
sensor_type = config.get('main','sensor_type')
sensor_pin  = int(config.get('main','sensor_pin'))

#start the daemon in the background
subprocess.Popen("/usr/bin/python rubustat_daemon.py start", shell=True)

# Setup the initial window
win = Tk()
myFont = tkFont.Font(family = 'Helvetica', size='14', weight = 'bold')
weatherFont = tkFont.Font(family = 'Helvetica', size='10', weight = 'bold')
scheduleFont = tkFont.Font(family = 'Helvetica', size='8', weight = 'bold')
win.title('Rubustat')
win.geometry('480x320')
win.configure(background='black', cursor='none')
# Production - no title bar
win.overrideredirect(1)

humidity = ''
indoorTemp = ''
targetTemp = ''
daemonStatus = ''
mode = ''
schedulename = ''
scheduleactive = 0

if weatherEnabled == True:
	def getWeather():
		gconn = sqlite3.connect("status.db")
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

def getWhatsOn():
#	if DEBUG == 1:
#		print "Called getWhatsOn\n"
	obStatus   = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(OB_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
	heatStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(HEATER_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
	coolStatus = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(AC_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())
	fanStatus  = int(subprocess.Popen("cat /sys/class/gpio/gpio" + str(FAN_PIN) + "/value", shell=True, stdout=subprocess.PIPE).stdout.read().strip())

	heatStringf.set("heat off")
	coolStringf.set("cool off")
	fanStringf.set("fan off")
	idleStringf.set("RUN")

	if AC_TYPE == 0:
		# Standard AC
		if heatStatus == PIN_ON:
			heatStringf.set("HEAT ON")
		if coolStatus == PIN_ON:
			coolStringf.set("COOL ON")
		if fanStatus == PIN_OFF:
			fanStringf.set("FAN ON")
	else:
		# Heat pump
		if heatStatus == PIN_ON:
			heatStringf.set("HEAT ON EMERGENCY")
		elif coolStatus == PIN_ON and obStatus == PIN_ON:
			heatStringf.set("HEAT ON")
		if coolStatus == PIN_ON and obStatus == PIN_OFF:
			coolStringf.set("COOL ON")
		if fanStatus == PIN_ON:
			fanStringf.set("FAN ON")

	if heatStatus == PIN_OFF and coolStatus == PIN_OFF and fanStatus == PIN_OFF:
		idleStringf.set("UNIT IDLE")
		idlestat.config(foreground='white')

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
#	if DEBUG == 1:
#		print "Called getStat\n"

	mode = ''
	targetTemp = 0
	gconn = sqlite3.connect("status.db")
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
	whatsOn.set(getWhatsOn())

	#find out what mode the system is in, and set the switch accordingly
	#the switch is in the "cool" position when the checkbox is checked

	daemonStatus=getDaemonStatus()
	return mode,targetTemp

if scheduleEnabled == True:
	def getSched():
		gconn = sqlite3.connect("status.db")
		found = False
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

def setStat():
	target = TargetTempf.get()
	mode = newmode.get()
	match = re.search(r'^\d{2}$',target)
	if match:
		if DEBUG == 1:
			print "Setting new mode, temp to: " + mode + ', ' + target

		gconn = sqlite3.connect("status.db")
		c = gconn.cursor()
		now = datetime.datetime.now()

		c.execute("DELETE FROM status")
		#c.execute("INSERT OR REPLACE INTO status (datetime,targetTemp,mode) VALUES (?,?,?)", (now, target, mode))
		c.execute("INSERT INTO status (datetime,targetTemp,mode) VALUES (?,?,?)", (now, target, mode))
		gconn.commit()
		gconn.close()

		if DEBUG == 1:
			print("New temperature of " + target + " set!")

		(mode,targetTemp) = getStat()
		newmode.set(mode)
		TargetTempf.set(targetTemp)
	else:
		if DEBUG == 1:
			print("That is not a two digit number! Try again!")

def updateTemp():
	global humidity, indoorTemp
#	if DEBUG == 1:
#		print "Called updateTemp\n"

	gconn = sqlite3.connect("status.db")
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

def get_sched(name):
	days = ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
	gconn = sqlite3.connect("schedule.db")
	c = gconn.cursor()
	for row in c.execute("SELECT name,startday,start,endday,end,low,high FROM schedule WHERE name='" + name + "'"):
		startday = days[row[1]]
		start    = row[2]
		endday   = days[row[3]]
		end      = row[4]
		low      = str(row[5])
		high     = str(row[6])
	gconn.close()

	return "starts " + startday + " at " + start + " and ends " + endday + " at " + end + " with min/max temp of " + low + "/" + high + "."

def disSched():
	if scheddisF.get() == 'enable':
		scheddisF.set('disable')
		newmode.set('cool')
	else:
		scheddisF.set('enable')
		newmode.set('off')
	setStat()

def confSched():
	print ""

def updateWhatsOn():
	return getWhatsOn()

def updateDaemonStatus():
	return getDaemonStatus()

# Increment or decrement temp setting based on the click of one of the arrow buttons
def incr():
	global targetTemp, TargetTempf
	targetTemp = str(int(targetTemp) + 1)
	TargetTempf.set(targetTemp)

def decr():
	global targetTemp, TargetTempf
	targetTemp = str(int(targetTemp) - 1)
	TargetTempf.set(targetTemp)

def change_color():
	current_text  = idleStringf.get()
	#if current_text == 'RUNNING':
	if current_text == 'UNIT IDLE':
		idlestat.config(foreground='white')
	else:
		current_color = idlestat.cget("foreground")
		if current_color == "black":
			next_color = "white"
		else:
			next_color = "black"
		idlestat.config(foreground=next_color)
		time.sleep(0.5)

def main():
	while True:
		(humidity,indoorTemp) = updateTemp()
		TargetTempf.set(targetTemp)
		humidityf.set(humidity)
		indoorTempf.set(indoorTemp)
		whatsOn.set(getWhatsOn())

		weatherstring = getWeather()
		Weatherf.set(weatherstring)

		if scheduleEnabled == True:
			(schedulename,scheduleactive) = getSched()
			if scheduleactive == True:
				tmpf = str(idleStringf.get())
				idleStringf.set('[' + schedulename + '] ' + tmpf)

				tmps = get_sched(schedulename)
				if newmode.get() == 'off':
					scheduleStatf.set('[' + schedulename + '] INACTIVE' + "\n" + tmps)
					scheddisF.set('enable')
				else:
					scheduleStatf.set('[' + schedulename + '] ACTIVE' + "\n" + tmps)
					scheddisF.set('disable')
			else:
				scheduleStatf.set('[none] active')
				scheddisF.set('enable')

		# Flash the status indicator
		change_color()

		win.update_idletasks()
		win.update()
		win.geometry(win.geometry())

# Form vars
humidityf   = StringVar()
TargetTempf = StringVar()
indoorTempf = StringVar()
newmode     = StringVar()
obStringf   = StringVar()
heatStringf = StringVar()
coolStringf = StringVar()
fanStringf  = StringVar()
idleStringf = StringVar()
Weatherf    = StringVar()
scheduleStatf = StringVar()
scheddisF   = StringVar()

# System vars
whatsOn = StringVar()
newTargetTemp = StringVar()

# Draw stuff
fill = Label(win,text="", width=1, bg='black', fg='white').grid(row=0,column=0,rowspan=10)

currentl = Label(win,text="Current temp", bg='black', fg='white').grid(row=0,column=1, sticky=E)
current = Entry(win, textvariable=indoorTempf, font='Helvetica 24 bold', width=4, bg='black', fg='white', border=0).grid(row=0,column=2, columnspan=2, sticky=W)
humidityl = Label(win,text="Current humidity", bg='black', fg='white').grid(row=0,column=4)
humidity = Entry(win, textvariable=humidityf, font='Helvetica 24 bold', width=4, bg='black', fg='white').grid(row=0,column=5, sticky=W)

fill2 = Label(win,text="", width=7, bg='black', fg='white').grid(row=2,column=0,columnspan=5)
#fill2 = Label(win,text="", width=7, bg='black', fg='white').grid(row=0,column=3,rowspan=10)

if AC_TYPE == 0:
	# Standard AC
	rb0 = Label(win,text="System Status", bg='black', fg='white').grid(row=3, column=1, columnspan=2, sticky=N)
	rb1 = Radiobutton(win, text='Heat',  variable=newmode, value='heat',  selectcolor='black', bg='black', fg='white').grid(row=4, column=1, sticky=NW)
	rb2 = Radiobutton(win, text='Cool',  variable=newmode, value='cool',  selectcolor='black', bg='black', fg='white').grid(row=5, column=1, sticky=NW)
	rb3 = Radiobutton(win, text='Off',   variable=newmode, value='off',   selectcolor='black', bg='black', fg='white').grid(row=6, columnspan=2, column=1, sticky=NW)
else:
	# Heat pump
	rb0 = Label(win,text="System Status", bg='black', fg='white').grid(row=3, column=1, columnspan=2, sticky=N)
	rb1 = Radiobutton(win, text='Heat',  variable=newmode, value='heat',  selectcolor='black', bg='black', fg='white').grid(row=4, column=1, sticky=NW)
	rb2 = Radiobutton(win, text='Cool',  variable=newmode, value='cool',  selectcolor='black', bg='black', fg='white').grid(row=5, column=1, sticky=NW)
	rb3 = Radiobutton(win, text='EHeat', variable=newmode, value='eheat', selectcolor='black', bg='black', fg='white').grid(row=6, column=1, sticky=NW)
	rb4 = Radiobutton(win, text='Off',   variable=newmode, value='off',   selectcolor='black', bg='black', fg='white').grid(row=7, column=1, sticky=NW)

heatstat = Label(win,textvariable=heatStringf, fg='red',   bg='black').grid(row=4, column=2, sticky=W)
coolstat = Label(win,textvariable=coolStringf, fg='cyan',  bg='black').grid(row=5, column=2, sticky=W)
fanstat  = Label(win,textvariable=fanStringf,  fg='green', bg='black').grid(row=6, column=2, sticky=W)
idlestat = Label(win,textvariable=idleStringf, fg='white', bg='black')
idlestat.grid(row=7, column=2, sticky=W)

fill2 = Label(win,text="", width=1, bg='black', fg='white').grid(row=0,column=3,rowspan=10)

templ = Label(win,text="Target temp", bg='black', fg='white').grid(row=3, column=4)
temp = Entry(win, textvariable=TargetTempf,font='Helvetica 28 bold', justify=CENTER, width=4, bg='black', fg='white').grid(row=4, rowspan=2, column=4, sticky=N)
arrowl = Button(win, text = '<', font = myFont, command = decr, bg='black', fg='white').grid(row=6, rowspan=2, column=4, sticky=SW)
arrowr = Button(win, text = '>', font = myFont, command = incr, bg='black', fg='white').grid(row=6, rowspan=2, column=4, sticky=SE)
goButton = Button(win, text = 'Go!', font = myFont, command = setStat, height = 2, width = 3, bg='black', fg='white').grid(row=4, rowspan=3, column=5, sticky=E)

fill3 = Label(win,text=" ", width=7, bg='black', fg='white').grid(row=8,column=0,columnspan=5)

if scheduleEnabled == True:
	weatherhead = Label(win,text='Current Conditions', font=myFont, bg='black', fg='white').grid(row=9,column=1, sticky=N, columnspan=2)
	weatherstat = Label(win,textvariable=Weatherf, font=weatherFont, bg='black', fg='white', wraplength=230).grid(row=10,column=1, sticky=N, columnspan=2, rowspan=2)

	schedulehead = Label(win,text='Schedule', font=myFont, bg='black', fg='white').grid(row=9,column=4, sticky=N, columnspan=2)
	schedulestat = Label(win,textvariable=scheduleStatf, font=scheduleFont, bg='black', fg='white', wraplength=200).grid(row=10,column=4, sticky=N, columnspan=2)
	scheddis     = Button(win, text='', textvariable=scheddisF, font=scheduleFont, command=disSched, height=1, width=2, bg='black', fg='white').grid(row=11, column=4, sticky=W)
	schedcon     = Button(win, text='config',  font=scheduleFont, command=confSched, height=1, width=2, bg='black', fg='white').grid(row=11, column=5, sticky=E)
else:
	weatherhead = Label(win,text='Current Conditions', font=myFont, bg='black', fg='white').grid(row=9, column=1, sticky=N, columnspan=5)
	weatherstat = Label(win,textvariable=Weatherf, font=weatherFont, bg='black', fg='white', wraplength=350).grid(row=10, column=1, sticky=N, columnspan=5, rowspan=2)

(mode,targetTemp) = getStat()
newmode.set(mode)
TargetTempf.set(targetTemp)

if __name__ == '__main__':
	main()
# vim: tabstop=4
