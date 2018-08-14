import paho.mqtt.client as mqtt
from utils import gen_client_id

broker_address = "10.0.2.15"
broker_port = 1883
keepalive = 60
client_id = None

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
	print("Connected with result code " + str(rc))
	client.subscribe("$SYS/#", qos=0)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
	print(msg.topic + ": " + str(msg.payload))

def on_log(client, userdata, level, buf):
	print("log: ",buf)

if not client_id:
	client_id = gen_client_id()
client = mqtt.Client(client_id=client_id, clean_session=True)
client.on_connect = on_connect
client.on_message = on_message
client.on_log = on_log

client.connect(host=broker_address, port=broker_port, keepalive=keepalive)

try:
	client.loop_forever()
except KeyboardInterrupt:
	client.disconnect()
	client.loop_stop()