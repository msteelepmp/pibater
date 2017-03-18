# coding=utf-8
import RPi.GPIO as GPIO
import LCD1602
import time
import logging
import wiringpi
import picamera

#######################
# Initalization steps
#######################

# Setup for HUMITURE dht11_dat()
HUMITURE_PIN = 17
GPIO.setmode(GPIO.BCM)  # Use the GPIOxx number scheme
MAX_UNCHANGE_COUNT = 100
STATE_INIT_PULL_DOWN = 1
STATE_INIT_PULL_UP = 2
STATE_DATA_FIRST_PULL_DOWN = 3
STATE_DATA_PULL_UP = 4
STATE_DATA_PULL_DOWN = 5

# Setup for relays
SERVO_RELAY_PIN = 5
GPIO.setup(SERVO_RELAY_PIN, GPIO.OUT)
LIGHT_RELAY_PIN = 6
GPIO.setup(LIGHT_RELAY_PIN, GPIO.OUT)
FAN_RELAY_PIN = 7
GPIO.setup(FAN_RELAY_PIN, GPIO.OUT)

# Setup for LCD
LCD1602.init(0x27, 1)  # init(slave address, background light)

# Setup for Servo controller
SERVO_CONTROL_PIN = 18
wiringpi.wiringPiSetupGpio()  # use 'GPIO naming'
wiringpi.pinMode(SERVO_CONTROL_PIN, wiringpi.GPIO.PWM_OUTPUT)
wiringpi.pwmSetMode(wiringpi.GPIO.PWM_MODE_MS)  # set the PWM mode to milliseconds stype
wiringpi.pwmSetClock(192)  # divide down clock
wiringpi.pwmSetRange(2000)

# Setup for Camera
PICTURE_FILENAME = 'pibatercam'

# Setup for basic logging
logging.basicConfig(filename='/var/log/pibater.log',
                    format='%(asctime)s %(message)s',
                    level=logging.DEBUG)

# Setup for logging
# Need to persist this value across executions of logging script
last_email_sent = 0

# Setup for main()
# Set initial temperature/humidity in case sensor isn't working
MAX_TEMP = 105
MIN_TEMP = 90
MAX_HUMIDITY = 70
MIN_HUMIDITY = 60
LEFT_DEGREES = 30
RIGHT_DEGREES = 120
NOTIFICATION_EMAIL = "msteele.pmp@gmail.com"
HUMIDITY_FUDGE = 4


def sendemail(message, subject, last_email_sent):
    # os.system('echo $message | mail NOTIFICATION_EMAIL -s "$subject" ')
    # Only send an email every hour
    if (time.time() - last_email_sent) > 3600:
        logging.info("Send email to %s. Message:%s" % (NOTIFICATION_EMAIL,message))
        last_email_sent = time.time()


'''
**********************************************************************
* Filename    : dht11.py
* Description : test for SunFoudner DHT11 humiture & temperature module
* Author      : Dream
* Brand       : SunFounder
* E-mail      : service@sunfounder.com
* Website     : www.sunfounder.com
* Update      : Dream    2016-09-30    New release
**********************************************************************
'''


def read_dht11_dat():
    GPIO.setup(HUMITURE_PIN, GPIO.OUT)
    GPIO.output(HUMITURE_PIN, GPIO.HIGH)
    time.sleep(0.05)
    GPIO.output(HUMITURE_PIN, GPIO.LOW)
    time.sleep(0.02)
    GPIO.setup(HUMITURE_PIN, GPIO.IN, GPIO.PUD_UP)

    unchanged_count = 0
    last = -1
    data = []
    while True:
        current = GPIO.input(HUMITURE_PIN)
        data.append(current)
        if last != current:
            unchanged_count = 0
            last = current
        else:
            unchanged_count += 1
            if unchanged_count > MAX_UNCHANGE_COUNT:
                break

    state = STATE_INIT_PULL_DOWN

    lengths = []
    current_length = 0

    for current in data:
        current_length += 1

        if state == STATE_INIT_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_INIT_PULL_UP
            else:
                continue
        if state == STATE_INIT_PULL_UP:
            if current == GPIO.HIGH:
                state = STATE_DATA_FIRST_PULL_DOWN
            else:
                continue
        if state == STATE_DATA_FIRST_PULL_DOWN:
            if current == GPIO.LOW:
                state = STATE_DATA_PULL_UP
            else:
                continue
        if state == STATE_DATA_PULL_UP:
            if current == GPIO.HIGH:
                current_length = 0
                state = STATE_DATA_PULL_DOWN
            else:
                continue
        if state == STATE_DATA_PULL_DOWN:
            if current == GPIO.LOW:
                lengths.append(current_length)
                state = STATE_DATA_PULL_UP
            else:
                continue
    if len(lengths) != 40:
        logging.warning("Humiture data not good, skip")
        return False

    shortest_pull_up = min(lengths)
    longest_pull_up = max(lengths)
    halfway = (longest_pull_up + shortest_pull_up) / 2
    bits = []
    the_bytes = []
    byte = 0

    for length in lengths:
        bit = 0
        if length > halfway:
            bit = 1
        bits.append(bit)
    # 	print "bits: %s, length: %d" % (bits, len(bits))
    for i in range(0, len(bits)):
        byte = byte << 1
        if (bits[i]):
            byte = byte | 1
        else:
            byte = byte | 0
        if ((i + 1) % 8 == 0):
            the_bytes.append(byte)
            byte = 0
        #	print the_bytes
    checksum = (the_bytes[0] + the_bytes[1] + the_bytes[2] + the_bytes[3]) & 0xFF
    if the_bytes[4] != checksum:
        logging.warning("Humiture data not good, skip")
        return False

    return the_bytes[0], the_bytes[2]  # returns humidity, temperature


def gethumiture(last_email_sent):
    result = False
    myresult = False
    cnt=0

    # Keep trying until we get a valid result
    while (result != False) and (cnt<10):
        cnt += 1
        for i in range(3):
           result = read_dht11_dat()
           if result:
               humidity, temperature = result
               if i == 0:
                   mytemp =95
                   myhumidity = 60
               fahrenheit_temp = 9.0/5.0 * temperature + 32
               mytemp = average(mytemp, fahrenheit_temp)
               myhumidity = average(myhumidity, humidity) 
               myresult = myhumidity, mytemp

    if result:
        logging.info("Humidity: %s%%,  Temperature: %s˚F" % (myhumidity, mytemp))
    else:
        # If we're never successful, send notifications
        sendemail('Can\'t get good humiture data after 5 tries', 
                  'Bad Humiture data',
                  last_email_sent)
        logging.warning("Humiture failed after 5 tries")

    return myresult


def rotate_eggs(degrees, camera):
    GPIO.output(SERVO_RELAY_PIN, GPIO.HIGH)
    if (degrees < 0) or (degrees > 180):
        logging.error("ERROR: Degrees=" + str(degrees) + " and is only allow to be 0-180 for servo")
        degrees = 0

    picfile = PICTURE_FILENAME + "." + gettime() + ".h264"

    GPIO.output(LIGHT_RELAY_PIN, GPIO.LOW)  # Light on
    camera.start_preview()
    time.sleep(3)  # Allow time for camera to stabilize
    camera.start_recording(picfile)
    pulse = degrees / 180 + 1
    wiringpi.pwmWrite(SERVO_CONTROL_PIN, pulse)
    time.sleep(8)
    camera.stop_recording()
    camera.stop_preview()
    GPIO.output(LIGHT_RELAY_PIN, GPIO.HIGH)  # Light on

    logging.info("Rotate eggs " + str(degrees) + "˚")


def gettime():
    return time.strftime("%Y%m%d %H:%M:%S %Z", time.localtime())


def hour():
    return time.strftime("%H", time.localtime())


def minutes():
    return time.strftime("%M", time.localtime())


def main():
    logging.info("****************** Starting pibater ****************** ")
    temp = 95  # Set initial values in case humiture doesn't work
    humidity = 65
    camera = picamera.PiCamera()

    GPIO.output(FAN_RELAY_PIN, GPIO.LOW)  # Turn on Fan
    rotate_eggs(LEFT_DEGREES, camera)  # Initialize the rotation, probably not necessary

    while True:

        # Since there are problems sometimes reading the humiture sensor,
        #   use the old value if gethumiture() returns false
        result = gethumiture(last_email_sent)
        if result != False:
            humidity, temp = result

        if temp < MIN_TEMP:
            GPIO.output(LIGHT_RELAY_PIN, GPIO.LOW)  # Light on
            logging.info("Temp: %s˚F, so turning light on" % temp)
        elif temp > MAX_TEMP:
            GPIO.output(LIGHT_RELAY_PIN, GPIO.HIGH)  # Light off
            logging.info("Temp: %s˚F, so turning light off" % temp)

        if (humidity < MIN_HUMIDITY) or (humidity > MAX_HUMIDITY):
            sendemail("Humidity out of the range:" + str(humidity) + "%%", 
                      "Humidity out of range.", 
                       last_email_sent)

        if int(hour()) % 3 == 0:  # If hour evenly divisible (mod) by 3
            if int(hour()) % 2 == 0:  # If even hour turn left
                rotate_eggs(LEFT_DEGREES, camera)
            else:
                rotate_eggs(RIGHT_DEGREES, camera)

        if int(minutes()) % 15 == 0:  # Take a picture every 15 minutes
            GPIO.output(LIGHT_RELAY_PIN, GPIO.LOW)  # Light on
            camera.capture(PICTURE_FILENAME + "." + gettime() + ".jpg")
            # Not ideal to turn the Light off if it was already on,
            #    but it'll turn on in the next min
            GPIO.output(LIGHT_RELAY_PIN, GPIO.HIGH)

        # Update LCD Message
        LCD1602.write(0, 0, gettime() + ' ' + str(temp) + '˚F ' + str(humidity) + '%')
        LCD1602.write(1, 1, 'Last activity')
        time.sleep(60)


def destroy():
    GPIO.output(SERVO_RELAY_PIN, GPIO.HIGH)  # Turn relay off
    GPIO.output(LIGHT_RELAY_PIN, GPIO.HIGH)  # Turn relay off
    GPIO.output(FAN_RELAY_PIN, GPIO.HIGH)  # Turn relay off
    GPIO.cleanup()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        destroy()
