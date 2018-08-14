import paho.mqtt.client as mqtt
import time
import datetime

from utils import gen_client_id
from random import randint

connected = False
broker_address = "10.0.2.15"
broker_port = 1883
keepalive = 60
client_id = "update_client"

sys_update = 60

connections = randint(3, 5)
messages_received = randint(194, 239)
messages_sent = randint(205, 328)
subscriptions = randint(4, 9)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        global connected
        connected = True
    else:
        pass

def on_log(mqttc, obj, level, string):
    print('Log: ' + string)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection")
    else:
        print("Disconnect cleanly")

def publish_updates():
    client.publish("$SYS/broker/clients/connected", connections, qos=0, retain=True)
    client.publish("$SYS/broker/messages/received", messages_received, qos=0, retain=True)
    client.publish("$SYS/broker/messages/sent", messages_sent, qos=0, retain=True)
    client.publish("$SYS/broker/subscriptions/count", subscriptions, qos=0, retain=True)

client = mqtt.Client(client_id=client_id, clean_session=True)

client.on_connect = on_connect
client.on_log = on_log
client.on_disconnect = on_disconnect

client.connect(host=broker_address, port=broker_port, keepalive=keepalive)

client.loop_start()
 
while not connected:
    time.sleep(1)


timestamp = datetime.datetime.fromtimestamp(time.time())
formated_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
client.publish('$SYS/broker/timestamp', formated_timestamp, qos=0, retain=True)
client.publish('$SYS/broker/version', "mosquitto version 1.4", qos=0, retain=True)

interval = 0

try:
    while True:
        if interval < sys_update:
            time.sleep(1)
            interval += 1
        else:
            publish_updates()
            interval = 0
except KeyboardInterrupt:
    client.disconnect()
    client.loop_stop()