from datetime import datetime

from dateutil import parser

test = "2025-02-17 00:00:00"

dt = parser.parse(test)

print(dt)

print(type(dt))

start_dt = datetime.strptime(test, "%Y-%m-%d %H:%M:%S")
print(start_dt)
print(type(start_dt))
