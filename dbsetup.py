import os
import subprocess
import sys
import sqlite3

# Simple utility to establish the basic database setup in case you are unable to run the daemon (for testing or work on the GUI, etc.)
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


