import paho.mqtt.client as mqtt
import time
from utils import gen_client_id
from random import randint

connected = False
broker_address = "10.0.2.15"
broker_port = 1883
keepalive = 60
client_id = "paho_livingroom_temp"

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
	if rc == 0:
		print("Connected to broker")
		global connected
		connected = True
	else:
		print("Connection failed")

def on_log(mqttc, obj, level, string):
    print('Log: ' + string)

def on_disconnect(client, userdata, rc):
	if rc != 0:
		print("Unexpected disconnection")
	else:
		print("Disconnect cleanly")

if not client_id:
	client_id = gen_client_id()
client = mqtt.Client(client_id=client_id, clean_session=True)

client.on_connect = on_connect
client.on_log = on_log
client.on_disconnect = on_disconnect

client.connect(host=broker_address, port=broker_port, keepalive=keepalive)

client.loop_start()
 
while not connected:
    time.sleep(1)

try:
	temp = randint(20, 23)
	while True:
		client.publish("home/kitchen/temp", str(temp), qos=0)
		time.sleep(60)
except KeyboardInterrupt:
	client.disconnect()
	client.loop_stop()