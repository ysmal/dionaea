import paho.mqtt.client as mqtt
import time
from utils import gen_client_id

connected = False
broker_address = "10.0.2.15"
broker_port = 1883
keepalive = 60

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
	if rc == 0:
		print("Connected to broker")
		global connected
		connected = True
	else:
		print("Connection failed")

client = mqtt.Client(client_id=gen_client_id(), clean_session=True)
client.on_connect = on_connect
client.connect(host=broker_address, port=broker_port, keepalive=keepalive)
client.loop_start()
 
while not connected:
    time.sleep(1)

try:
	while True:
		client.publish("home/kitchen/temp", "20")
		time.sleep(3)
except KeyboardInterrupt:
	client.disconnect()
	client.loop_stop()