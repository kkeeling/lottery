#!/usr/bin/env python
import os
import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print('Waiting for Postgres server to be available...')
while True:
    try:
        s.connect((os.environ['LOTTERY_DB'], 5432))
        s.close()
        break
    except socket.error as ex:
        time.sleep(0.1)
