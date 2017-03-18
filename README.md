# pibater
Raspberry Pi Chicken incubator

This is Python code that attempts to control for temperature and egg rotation for incubating chickens. It will also alert if the humidity is out of range and take pictures every 15 min.

I am running a Raspberry Pi 3 with the RPi Camera2, SunFoundery Humiture sensor and relay, and a TowerPro 9G servo. Relays control power to the servo (so that it's not running all of the time), lamp (for heat and camera), circulation fan (which runs all of the time).

This is also my first Python project. So any hints or suggestions would be appreciated. I kept it simple, with no OO concepts in hopes that my 10 year old could follow and update the code.
