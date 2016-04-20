#!/usr/bin/python

import sqlite3
import datetime
import ConfigParser
#import calendar
#import pprint
from operator import itemgetter

config = ConfigParser.ConfigParser()
config.read("config.txt")

DEBUG = int(config.get('main','DEBUG'))
class schedule():
	days = ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
	months = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
	current = ()
	working = {}
	schedules = []

	def __init__(self):
		scconn = sqlite3.connect("schedule.db")
		c = scconn.cursor()
		c.execute('CREATE TABLE IF NOT EXISTS schedule (name TEXT, startday INT, start TIMESTAMP, endday INT, end TIMESTAMP, low FLOAT, high FLOAT)')
		#c.execute('INSERT INTO schedule VALUES(?,?,?,?,?,?,?)', ('Away',   1,'06:30:00',1,'17:00:00',65.0,77.0))
		#c.execute('INSERT INTO schedule VALUES(?,?,?,?,?,?,?)', ('Home',   1,'17:00:00',1,'23:30:00',67.0,74.0))
		#c.execute('INSERT INTO schedule VALUES(?,?,?,?,?,?,?)', ('Night',  1,'23:30:00',1,'04:30:00',66.0,75.0))
		#c.execute('INSERT INTO schedule VALUES(?,?,?,?,?,?,?)', ('Weekend',6,'23:30:00',0,'04:30:00',66.0,75.0))
		#scconn.commit()
		scconn.close()

		self.read_schedule()
		#self.set_current()

	def read_schedule(self):
		scconn = sqlite3.connect("schedule.db")
		c = scconn.cursor()

		i = 0
		for row in c.execute('SELECT name,startday,start,endday,end,low,high FROM schedule'):
			out = list(row)
			out.insert(0,i)
			row = tuple(out)
			self.schedules.extend({row})
			i = i + 1

		scconn.close()

	def get_one(self,name):
		scconn = sqlite3.connect("schedule.db")
		c = scconn.cursor()
		for row in c.execute("SELECT name,startday,start,endday,end,low,high FROM schedule WHERE name='" + name + "'"):
			startday = row[1]
			start    = row[2] 
			endday   = row[3]
			end      = row[4]
			low      = row[5]
			high     = row[6]
		scconn.close()
		return (name,startday,start,endday,end,low,high)

	def print_schedule(self):
		for schedule in self.schedules:
			name = itemgetter(1)(schedule)
			startday = self.days[itemgetter(2)(schedule)]
			start = itemgetter(3)(schedule)
			endday = self.days[itemgetter(4)(schedule)]
			end   = itemgetter(5)(schedule)
			low   = str(itemgetter(6)(schedule))
			high  = str(itemgetter(7)(schedule))
			print name + ": starts " + startday + " at " + start + " and ends " + endday + " at " + end + " with min/max temp of " + low + "/" + high + "."

	def set_schedule(self):
		if working:
			c.execute("INSERT OR REPLACE INTO schedule (name,startday,start,endday,end,low,high) VALUES (?,?,?,?,?,?,?)", working)

	def check_schedule(self):
		self.set_current()
		if self.current:
			if DEBUG == 1:
				print "Schedule currently in action!"
				print schedule

	def set_current(self):
		# Set the current schedule based on the current date, time, and available schedules
		now = datetime.datetime.now()
		year  = now.year
		month = now.month
		today = now.weekday()
		hour  = now.hour
		minute = now.minute

		mytimestr = str(hour).zfill(2) + ':' + str(minute).zfill(2) + ':00'
		mytime    = datetime.datetime.strptime(mytimestr, '%H:%M:%S')

		print "Today is " + self.days[today] + " and the time is " + mytimestr
		for schedule in self.schedules:
			if itemgetter(2)(schedule) == today:
				if DEBUG == 1:
					print "Schedule START match for " + itemgetter(1)(schedule)
				if itemgetter(3)(schedule) == mytimestr:
					# pointless
					if DEBUG == 1:
						print "Schedule match for right now!"
				elif itemgetter(3)(schedule) < mytimestr:
					if DEBUG == 1:
						print "a. We are in this window now!"
						print "a. start < now"
					self.current = schedule
			elif itemgetter(4)(schedule) == today:
				if DEBUG == 1:
					print "Schedule end match for " + itemgetter(1)(schedule)
				if itemgetter(5)(schedule) == mytimestr:
					# pointless
					if DEBUG == 1:
						print "Schedule match for right now!"
				elif mytimestr < itemgetter(5)(schedule):
					if DEBUG == 1:
						print "b. We are in this window now!"
						print "b. now < end"
					self.current = schedule


