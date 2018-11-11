""" 
dht22.py 
Temperature/Humidity monitor using Raspberry Pi and DHT22. 
Data is displayed at thingspeak.com
Original author: Mahesh Venkitachalam at electronut.in 
Modified by Adam Garbo on December 1, 2016 

Support of DHT22 in Python 3: https://github.com/adafruit/Adafruit_Python_DHT
Filter to avoid spurious values: https://forum.dexterindustries.com/t/solved-dht-sensor-occasionally-returning-spurious-values/2939/5
urllib python2->python3: https://stackoverflow.com/questions/2792650/import-error-no-module-name-urllib2

Ideas:
1) Done - Create a filter function to get rid of false peaks from sensors
2) Done - Make the functionaly as function humidity instead of timing (need data to be exchanged between python scripts).
3) Done - Send on/off data to Thingspeak in order to see if the engine should be on or off (relay status)
4) Send an email if any malfunction is detected
5) Detect and present sensor errors, compare the two sensors
6) Done - Detect two/three/several values below stop criteria in a row before stopping the engine
7) Force start engine after 6 hours and let it run until it stops by itself (lowest humidity)
8) Error: Once in a while the values are getting low in a single peak. Test the different error conditions and how these are handled.
9) Done - Count number of hours the engine has been running and idle (accumulated
 values)
10) Create an error log to store when the system has ben resetting and detecting different issues
11) Done - Enginge on and off counter must be minutes and not iterations
12) Done - The counter uploaded for thingspeak must contain a status counter instead (minutes in latest state).
13) Read sensors in a thread configured for sensor a and b with parametre.
14) Make myAPI dependant on the IP Addr in order to make the device in Søndervig running on same codebase.
15) The state is not correct during startup. If the engine is running and you restart - then the status is OFF even though the engine is running :-)
"""

import sys 
import RPi.GPIO as GPIO 
from time import sleep
import time
import datetime
from datetime import datetime
import Adafruit_DHT 
#import urllib2 #Python 2
import urllib.request #Python 3
#datetime.datetime.now()
myAPI_LSV33 = "07NQR132PCXPDSGD"      #Used for Søndervig account
myAPI_TestACC = "LQYHZ7MCQR6SK6T8"      #Used for Testbench account

#Raspberry PI Serials
SerialNoWIFI = '000000006473aedd'
SerialNewest = '000000002efbf320'
SerialLSV33 = '000000001296c725'         #OldRaspberry pi - placed in Søndervig

#Hardware Pins
OC_11 = 17                              #GPIO 17 (open collector for reset of sensor 9)
OC_13 = 27                              #GPIO 27 (open collector for reset of sensor 10)
RELAY = 20
sensor = 9  # The Sensor goes on digital port 4.

GPIO.setmode(GPIO.BCM)             # choose BCM or BOARD
GPIO.setup(OC_11, GPIO.OUT)           # GREEN LED set GPIO as an output
GPIO.setup(OC_13, GPIO.OUT)           # GREEN LED set GPIO as an output
GPIO.setup(RELAY, GPIO.OUT)           # RELAY set GPIO as an output

#Logic definitions
ON = 1
OFF = 0
FALSE = 0
TRUE = 1

import math
import numpy
import threading
from datetime import datetime

# temp_humidity_sensor_type
blue = 0    # The Blue colored sensor.
white = 1   # The White colored sensor.

filtered_temperature_Sensor9 = [] # here we keep the temperature values after removing outliers
filtered_humidity_Sensor9 = [] # here we keep the filtered humidity values after removing the outliers
filtered_temperature_Sensor10 = [] # here we keep the temperature values after removing outliers
filtered_humidity_Sensor10 = [] # here we keep the filtered humidity values after removing the outliers

lock = threading.Lock() # we are using locks so we don't have conflicts while accessing the shared variables
event = threading.Event() # we are using an event so we can close the thread as soon as KeyboardInterrupt is raised

# This function read and return the unique serial number in the Raspberry PI
def getserial():
  # Extract serial from cpuinfo file
  cpuserial = "0000000000000000"
  try:
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:6]=='Serial':
        cpuserial = line[10:26]
    f.close()
  except:
    cpuserial = "ERROR000000000"
  return cpuserial



# function which eliminates the noise
# by using a statistical model
# we determine the standard normal deviation and we exclude anything that goes beyond a threshold
# think of a probability distribution plot - we remove the extremes
# the greater the std_factor, the more "forgiving" is the algorithm with the extreme values
def eliminateNoise(values, std_factor = 2):
    mean = numpy.mean(values)
    standard_deviation = numpy.std(values)

    if standard_deviation == 0:
        return values

    final_values = [element for element in values if element > mean - std_factor * standard_deviation]
    final_values = [element for element in final_values if element < mean + std_factor * standard_deviation]

    return final_values

# function for processing the data
# filtering, periods of time, yada yada
def readingValues(SensorToUse, ResetPin):
    seconds_window = 10 # after this many second we make a record
    SensorCounter = 0
    values = []
    a=1
    b=-4.2
    MeasuredValidDataInARow = 0
    MeasuredInvalidInARow = 0
    
    while not event.is_set():
        counter = 0
        
        while counter < seconds_window and not event.is_set():
            temp = None
            humidity = None
            MeasuredValuedIsInvalid = 1   #Assume invalid data
            try:                
                lock.acquire()
                [humidity, temp] = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, SensorToUse)
                lock.release()
            except IOError:
                print("Execption! IO error on sensor - continue.")
            print("RawData hum, tmp:", humidity, temp)

            if(SensorToUse == 10):
                humidity = humidity+b
            SensorCounter +=1    
           
            if(str(temp) == "None" or str(humidity) == "None"): #Error - reset DHT and continue
                print("Sensor X returns None:", SensorToUse)
                GPIO.setup(ResetPin, GPIO.OUT)           # GREEN LED set GPIO24 as an output
                GPIO.output(ResetPin, OFF)       #Sensor 9 OFF
                sleep(0.1)
                GPIO.output(ResetPin, ON)        #Sensor 9 ON
                MeasuredValuedIsInvalid = 1
            else:
                if(humidity > 100 or temp > 50):
                    print("Reset Sensor")
                    GPIO.setup(ResetPin, GPIO.OUT)           # GREEN LED set GPIO24 as an output
                    GPIO.output(ResetPin, OFF)       #Sensor 9 OFF
                    sleep(0.1)
                    GPIO.output(ResetPin, ON)        #Sensor 9 ON
                    MeasuredValuedIsInvalid = 1
                else:
                    math.isnan(temp) == False and math.isnan(humidity) == False
                    values.append({"temp" : temp, "hum" : humidity})
                    counter += 1
                    MeasuredValuedIsInvalid = 0   #Data is valid
            
        if(MeasuredValuedIsInvalid == 0): #Use values if data is valid
            MeasuredInvalidInARow = 0
            MeasuredValidDataInARow +=1
            
            if(SensorToUse == 9):
                lock.acquire()
                filtered_temperature_Sensor9.append(numpy.mean(eliminateNoise([x["temp"] for x in values])))
                filtered_humidity_Sensor9.append(numpy.mean(eliminateNoise([x["hum"] for x in values])))
                lock.release()
            values = []
        else:
            MeasuredValidDataInARow = 0
            MeasuredInvalidInARow +=1 #Increment value
            print("MeasuredInvalidInARow:", MeasuredInvalidInARow)
            print("MeasuredValidInARow:", MeasuredValidDataInARow)
            
def Main():
    # here we start the thread
    # we use a thread in order to gather/process the data separately from the printing proceess
    data_collector_Sens9 = threading.Thread(name='ReadSensor9', target = readingValues, args=(9,OC_11,))
    data_collector_Sens9.start()
#    data_collector_Sens10 = threading.Thread(name='ReadSensor10', target = readingValues, args=(10, OC_13,))
#    data_collector_Sens10.start()

    MaxHumidityBeforeStart = 66 #Humidty to exceed efore engine starts 181111 ELT: 63->66
    MinHumidityBeforeStop = 60 #Humdity before engine stops 181111 ELT: 57->60
    EngineStatus = "OFF"
    OldEngineStatus = "OFF"
    EngineOn = 0
    EngineOnCounter = 0
    EngineOffCounter = 0
    humidityLowCounter = 0
    humidityHighCounter = 0
    SecCounter = 0
    OldDateTime = time.time()  
    PISerialNumber = 0
    
    
    while not event.is_set():
        if(PISerialNumber == 0):
          PISerialNumber = getserial()   #Fetch the unique ID
          print("Serial: ", PISerialNumber) 
          if(PISerialNumber == SerialNoWIFI):
            print("Raspberry Identified: RaspberryNoWIFI")
            baseURL = 'https://api.thingspeak.com/update?api_key=%s' % myAPI_TestACC 
          if(PISerialNumber == SerialNewest):
            print("Raspberry Identified: RaspberryNewest")
            baseURL = 'https://api.thingspeak.com/update?api_key=%s' % myAPI_TestACC
          if(PISerialNumber == SerialLSV33):
            print("Raspberry Identified: OldRaspberry")
            baseURL = 'https://api.thingspeak.com/update?api_key=%s' % myAPI_LSV33
            
        if len(filtered_humidity_Sensor9) > 0: # or we could have used filtered_temperature instead
            # here you can do whatever you want with the variables: print them, file them out, anything
            temperature_Sensor9 = filtered_temperature_Sensor9.pop()
            humidity_Sensor9 = filtered_humidity_Sensor9.pop()
            print('{},{:.01f},{:.01f}' .format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), temperature_Sensor9, humidity_Sensor9))
            
            #   EngineControl 
            if(humidity_Sensor9 > MaxHumidityBeforeStart):# and EngineStatus == "OFF"):
                if(humidityHighCounter > 2):
                    GPIO.output(RELAY, ON)                  # RELAY set GPIO24 to 1/GPIO.HIGH/True  
                    EngineStatus = "ON"
                    EngineOn = 1                    
                    EngineOffCounter = 0
                    humidityLowCounter = 0
                humidityHighCounter += 1
            else:
                humidityHighCounter = 0
                
            if(humidity_Sensor9 < MinHumidityBeforeStop):# and EngineStatus == "ON"):
                if(humidityLowCounter > 2):
                    GPIO.output(RELAY, OFF)                  # RELAY set GPIO24 to 1/GPIO.HIGH/True  
                    EngineStatus = "OFF"
                    EngineOn = 0                  
                    EngineOnCounter = 0
                    humidityHighCounter = 0
                humidityLowCounter += 1
            else:
                humidityLowCounter = 0
                
            print("Filtered Hum, Tmp:", humidity_Sensor9, temperature_Sensor9)
            print("EngineStatus:", EngineStatus)
            print("EngineOn:", EngineOn)
            print("EngineOnCounter:",EngineOnCounter)
            print("EngineOffCounter:",EngineOffCounter)
            print("HumidityLowCounter:",humidityLowCounter)
            print("HumidityHighCounter:",humidityHighCounter)

            try:
               if(EngineStatus == "ON"):  #Enginge is ON
                    f = urllib.request.urlopen(baseURL + "&field1=%s&field2=%s&field3=%s&field4=%s&field5=%s" % (humidity_Sensor9, temperature_Sensor9, EngineOn, EngineOnCounter, EngineOffCounter))
               else:
                    f = urllib.request.urlopen(baseURL + "&field1=%s&field2=%s&field3=%s&field4=%s&field5=%s" % (humidity_Sensor9, temperature_Sensor9, EngineOn, EngineOffCounter, EngineOnCounter))
               print(f.read()) 
               f.close() 

            except:
               print("Exeception! Connection to Thingspeak couldn't be established - just continue...")
            
            print("------------------------------------------------")
        
#        sleep(3)
        if(OldEngineStatus != EngineStatus):
            OldDateTime = time.time()  #Store datetime
            OldEngingStatus = EngineStatus  #EngineStatus is updated, store OldStatus    
        
        if(EngineStatus == "OFF"):  #Enginge is OFF
            EngineOffCounter = round((time.time()-OldDateTime)/60,1)        #Increment off counter
        else:
            EngineOnCounter = round((time.time()-OldDateTime)/60,1)        #Increment on counter
        sleep(30)
    # wait until the thread is finished
    data_collector_Sens9.join()


if __name__ == "__main__":
    try:
        Main()

    except KeyboardInterrupt:
        event.set()
