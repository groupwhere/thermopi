import Adafruit_DHT
from getIndoorTemp import getIndoorTemp
# Simple utility program to check the temperature from your sensor
# Adafruit DHT11 and others
sensor_type = 'DHT_11';
sensor_pin  = 14

def updateTemp():
    if sensor_type == 'DHT_11':
        sensor = 11
        humidity, temperature = Adafruit_DHT.read_retry(sensor, sensor_pin)
        indoorTemp = float(temperature * 9/5.0 + 32)
    else:
        humidity = ''
        indoorTemp = float(getIndoorTemp())

    print "Indoor Temp: " + str(indoorTemp) + ", Humidity: " + str(humidity) + "\n"

updateTemp()
