#!/bin/bash

# Launch clients in background with nohup ($! represents the PID of the last process executed):
nohup python client_subscribe.py >& /dev/null &
echo $! > client_sub_pid.txt

nohup python client_publish_bedroom.py >& /dev/null &
echo $! > client_pub_pid.txt