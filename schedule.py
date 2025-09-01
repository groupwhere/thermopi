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
    def __init__(self):
        self.holding = False
        self.active = False
        #               0         1        2          3           4         5         6
        self.days = ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
        self.caldays = {'week' : ['Mo','Tu','We','Th','Fr','Sa','Su']}
        self.months = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
        self.current = ()
        self.working = {}
        # Schedules are activation periods for settings. The name field matches a setting name.
        self.schedules = []
        # Settings establish low and high temperatures for activating the AC unit.  They are scheduled by schedules with a matching name.
        self.settings = []

        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()

        # Verify existence of tables
        c.execute('CREATE TABLE IF NOT EXISTS settings (sename TEXT, low FLOAT, high FLOAT)')
        c.execute('CREATE TABLE IF NOT EXISTS schedule (scname TEXT, startday INT, start TIMESTAMP, endday INT, end TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS activation (active BOOL)')
        c.execute('CREATE TABLE IF NOT EXISTS holding (hold TEXT)')

        # Check for empty (new) settings table
        c.execute("SELECT COUNT(sename) FROM settings")
        row = c.fetchone()[0]
        if row == 0:
            c.execute('INSERT INTO settings VALUES(?,?,?)', ('Away',   65.0,77.0))
            c.execute('INSERT INTO settings VALUES(?,?,?)', ('Home',   67.0,74.0))
            c.execute('INSERT INTO settings VALUES(?,?,?)', ('Night',  66.0,75.0))
            c.execute('INSERT INTO settings VALUES(?,?,?)', ('Weekend',66.0,75.0))
            scconn.commit()

        # Check for empty (new) schedule table
        c.execute("SELECT COUNT(scname) FROM schedule")
        row = c.fetchone()[0]
        if row == 0:
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Away',   0,'06:30:00',0,'17:00:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Away',   1,'06:30:00',1,'17:00:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Away',   2,'06:30:00',2,'17:00:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Away',   3,'06:30:00',3,'17:00:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Away',   4,'06:30:00',4,'17:00:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Home',   0,'17:00:00',0,'23:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Home',   1,'17:00:00',1,'23:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Home',   2,'17:00:00',2,'23:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Home',   3,'17:00:00',3,'23:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Home',   4,'17:00:00',4,'23:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Night',  6,'23:30:00',0,'04:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Night',  0,'23:30:00',1,'04:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Night',  1,'23:30:00',2,'04:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Night',  2,'23:30:00',3,'04:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Night',  3,'23:30:00',4,'04:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Night',  4,'23:30:00',5,'04:30:00'))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Weekend',5,'04:30:00',-1,''))
            c.execute('INSERT INTO schedule VALUES(?,?,?,?,?)', ('Weekend',-1,'',6,'23:30:00'))
            scconn.commit()
        scconn.close()

        #self.read_schedule()
        #self.set_current()

    def read_schedule(self):
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        d = scconn.cursor()
        self.schedules = []
        self.settings  = []

        # Populate schedule as combination of schedule and settings
        for row in c.execute('SELECT schedule.scname,schedule.startday,schedule.start,schedule.endday,schedule.end,settings.low,settings.high FROM schedule INNER JOIN settings ON settings.sename = schedule.scname'):
            self.schedules.extend({row})

        # Populate settings alone
        for row in d.execute('SELECT sename,low,high FROM settings'):
            self.settings.extend({row})

        for row in c.execute('SELECT active FROM activation'):
            self.active = row[0]
#        print self.settings
#        print self.schedules
        scconn.close()
        self.clean_schedule()
        self.check_hold()

    # Merge days for schedules crossing over midnight
    #   For example, a schedule starts Friday 6pm and ends Sunday 3am.  The database will have two lines.
    #   This function merges those into one schedule line
    def clean_schedule(self):
        found = bool()
        out = []
        for pschedule in self.schedules:
            for schedule in self.schedules:
                found = False
                if schedule[0] == pschedule[0] and schedule[1] == -1 and pschedule[3] == -1 and schedule != pschedule:
                    temp = (schedule[0], pschedule[1], pschedule[2], schedule[3], schedule[4], schedule[5], schedule[6])
                    out.extend({temp})
                    found = True
            if found == False and pschedule[1] != -1 and pschedule[3] != -1:
                out.extend({pschedule})
        self.schedules = out

    def check_hold(self):
        hold = ''
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        for row in c.execute('SELECT hold FROM holding'):
            hold = row[0]
        if hold:
            self.hold(hold)
        else:
            self.holding = False
        scconn.close()

    def nohold(self):
        self.holding = False
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        c.execute('DELETE FROM holding');
        scconn.commit()
        scconn.close()
        self.set_current()

        if DEBUG > 0:
            print "schedule.nohold: Schedule override removed." 

    def hold(self,name):
        # Set and hold a schedule setting (override schedule)
        #(u'Away', 2, u'06:30:00', 1, u'17:00:00', 65.0, 77.0)
        now = datetime.datetime.now()
        today = now.weekday()
        res = filter(lambda t: t[0] == name, self.settings)
        #print res[0]

        newres = [(res[0][0], today, '0:00:00', today, '23:59:59', res[0][1], res[0][2])]
        self.current = newres

        self.holding = True
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        c.execute('DELETE FROM holding');
        scconn.commit()
        c.execute('INSERT INTO holding(hold) VALUES (?)', (name,))
        scconn.commit()
        scconn.close()
        if DEBUG > 0:
            print "schedule.hold: Override schedule and set: " + name
            print res

    def del_setting(self,name):
        if DEBUG > 0:
            print "schedule.del_setting: Deleting: " + name
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        c.execute("DELETE FROM settings WHERE sename=?", (name,))
        c.execute("DELETE FROM schedule WHERE scname=?", (name,))
        scconn.commit()
        scconn.close()
        self.read_schedule()

        return True

    def save_setting(self,setting,new):
        if setting[0] and setting[1] and setting[2]:
            scconn = sqlite3.connect("schedule.db")
            c = scconn.cursor()
            if new == True:
                c.execute("INSERT INTO settings (sename,low,high) VALUES (?,?,?)", (setting[0],float(setting[1]),float(setting[2])))
            else:
                c.execute("UPDATE settings SET low=?,high=? WHERE sename=?", (float(setting[1]),float(setting[2]),setting[0]))
            scconn.commit()
            scconn.close()
            self.read_schedule()
            return True
        else:
            print "schedule.savesetting: bad data!"
            return False

    def save_schedule(self,setting,new,start,end):
        if DEBUG > 0:
            print "schedule.save_schedule:"
            print setting
            print start
            print end

        if setting[0] and setting[1] and setting[2]:
            scconn = sqlite3.connect("schedule.db")
            c = scconn.cursor()
            if new == True:
                if DEBUG > 0:
                    print "schedule.save_schedule: INSERT INTO settings (sename,low,high) VALUES (?,?,?)", (setting[0],float(setting[1]),float(setting[2]))
                c.execute("INSERT INTO settings (sename,low,high) VALUES (?,?,?)", (setting[0],float(setting[1]),float(setting[2])))
            else:
                if DEBUG > 0:
                    print "schedule.save_schedule: UPDATE settings SET low=?,high=? WHERE sename=?", (float(setting[1]),float(setting[2]),setting[0])
                c.execute("UPDATE settings SET low=?,high=? WHERE sename=?", (float(setting[1]),float(setting[2]),setting[0]))
                scconn.commit()

            c.execute("DELETE FROM schedule WHERE scname='" + setting[0] + "'")
            scconn.commit()

            # For each day 0-6 (until 7)
            for i in range(0,7):
                startday = i
                endday = i
                print "schedule.save_schedule: Checking schedule " + setting[0] + " for " + self.days[i]
                if start[i] == '' and end[i] == '':
                    if DEBUG > 0:
                        print "schedule.save_schedule: Start and end times cancelled. No new data to insert."
                    continue
                elif start[i] == 'X' and end[i] == 'X':
                    if DEBUG > 0:
                        print "schedule.save_schedule: Start and end times cancelled. No new data to insert."
                    continue
                elif start[i] == 'X' or start[i] == '':
                    startday = -1
                    start[i] = ''
                    if len(end[i]) < 8:
                        end[i] = end[i] + ':00'
                elif end[i] == 'X' or end[i] == '':
                    endday = -1
                    end[i] = ''
                    if len(start[i]) < 8:
                        start[i] = start[i] + ':00'
                else:
                    if len(start[i]) < 8:
                        start[i] = start[i] + ':00'
                    if len(end[i]) < 8:
                        end[i] = end[i] + ':00'
                if DEBUG > 0:
                    print "schedule.save_schedule: start[i] and end[i] present..." + start[i] + ", " + end[i]
                c.execute('INSERT INTO schedule VALUES (?,?,?,?,?)', (setting[0], startday, start[i], endday, end[i]))
                scconn.commit()

            scconn.close()
            self.read_schedule()
            return True
        else:
            print "schedule.save_schedule: bad data!"
            return False

    def get_one(self,name):
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        for row in c.execute("SELECT scname,startday,start,endday,end FROM schedule WHERE scname='" + name + "'"):
            startday = row[1]
            start    = row[2]
            endday   = row[3]
            end      = row[4]
        scconn.close()
        return (name,startday,start,endday,end)

    def get_one_day(self,name,day):
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        for row in c.execute("SELECT scname,startday,start,endday,end FROM schedule WHERE scname='" + name + "' AND (startday=? OR endday=?)",(day,day,)):
            startday = row[1]
            start    = row[2]
            endday   = row[3]
            end      = row[4]
            scconn.close()
            return (name,startday,start,endday,end)
        return ()

    def print_schedule(self):
        for schedule in self.schedules:
            setting = schedule
            name = itemgetter(0)(schedule)
            startday = self.days[itemgetter(1)(schedule)]
            start = itemgetter(2)(schedule)
            endday = self.days[itemgetter(3)(schedule)]
            end   = itemgetter(4)(schedule)
            low   = str(itemgetter(5)(schedule))
            high  = str(itemgetter(6)(schedule))
            print name + ": starts " + startday + " at " + start + " and ends " + endday + " at " + end + " with min/max temp of " + low + "/" + high + "."

    def set_schedule(self):
        if working:
            c.execute("INSERT OR REPLACE INTO schedule (name,startday,start,endday,end,low,high) VALUES (?,?,?,?,?,?,?)", working)

    def check_schedule(self):
        self.set_current()
        if self.current:
            if DEBUG > 0:
                if self.active == True:
                    print "schedule.check_schedule: Schedule currently active!"
                else:
                    print "schedule.check_schedule: Schedule currently inactive!"
                print schedule

    def save_active(self):
        if DEBUG > 0:
            print "schedule.save_active(" + str(self.active) + ")"
        scconn = sqlite3.connect("schedule.db")
        c = scconn.cursor()
        c.execute('DELETE FROM activation');
        scconn.commit()
        c.execute('INSERT INTO activation (active) VALUES (?)', (self.active,))
        scconn.commit()
        scconn.close()

    def set_active(self):
        if DEBUG > 0:
            print "schedule.set_active: Setting schedule to active."
        self.active = True
        self.save_active()

    def set_inactive(self):
        if DEBUG > 0:
            print "schedule.set_inactive: Setting schedule to inactive."
        self.active = False
        self.save_active()

    def set_current(self):
        if self.holding == True:
            if DEBUG > 0:
                print "schedule.set_current: Schedule hold set to "
                print self.current
            return self.current
        # Set the current schedule based on the current date, time, and available schedules
        now = datetime.datetime.now()
        year  = now.year
        month = now.month
        today = now.weekday()
        hour  = now.hour
        minute = now.minute

        mytimestr = str(hour).zfill(2) + ':' + str(minute).zfill(2) + ':00'
        mytime    = datetime.datetime.strptime(mytimestr, '%H:%M:%S')

        if len(self.schedules) == 0:
            self.read_schedule()

        if DEBUG > 1:
            print "schedule.set_current: Today is " + self.days[today] + "(" + str(today) + ") and the time is " + mytimestr

        for schedule in self.schedules:
            if DEBUG > 1:
                print "schedule.set_current: Checking: " + str(schedule)
            if itemgetter(1)(schedule) == today:
                #(u'Away', 2, u'06:30:00', 1, u'17:00:00', 65.0, 77.0)
                if DEBUG > 1:
                    print "schedule.set_current: Schedule START match for " + itemgetter(0)(schedule) + " on " + self.days[itemgetter(1)(schedule)]
                if itemgetter(2)(schedule) == mytimestr:
                    # pointless
                    if DEBUG > 1:
                        print "schedule.set_current: Schedule match for right now!"
                elif itemgetter(2)(schedule) < mytimestr and mytimestr < itemgetter(4)(schedule):
                    if DEBUG > 1:
                        print "schedule.set_current: a. We are in this window now!"
                        print "schedule.set_current: a. start at: " + itemgetter(2)(schedule) + " < now: " + mytimestr
                    self.current = schedule
                    break
                elif int(itemgetter(3)(schedule)) == int(itemgetter(1)(schedule)) + 1:
                    if DEBUG > 1:
                        print "schedule.set_current: a. We are in this window now!"
                        print "schedule.set_current: a. Ends after today"
                    self.current = schedule
                    break
                else:
                    if DEBUG > 1:
                        print "schedule.set_current: a. No end match.  NOT in this schedule..."
            elif itemgetter(3)(schedule) == today:
                if DEBUG > 1:
                    print "schedule.set_current: Schedule END match for " + itemgetter(0)(schedule)
                if itemgetter(4)(schedule) == mytimestr:
                    # pointless
                    if DEBUG > 1:
                        print "schedule.set_current: Schedule match for right now!"
                elif mytimestr < itemgetter(4)(schedule) and itemgetter(2)(schedule) < mytimestr:
                    if DEBUG > 1:
                        print "schedule.set_current: b. We are in this window now!"
                        print "schedule.set_current: b. now: " + mytimestr + " < end at: " + itemgetter(4)(schedule)
                    self.current = schedule
                    break
                else:
                    if DEBUG > 1:
                        print "schedule.set_current: b. NOT in this schedule..."

        return self.current

tschedule = schedule()
tschedule.read_schedule()
#tschedule.print_schedule()
#tschedule.hold('Home')
tschedule.set_current()
#print tschedule.current
#print tschedule.schedules
#print tschedule.settings
#print tschedule.settings[0][0]
