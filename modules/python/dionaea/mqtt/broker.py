import logging

logger = logging.getLogger('mqtt')

subscriptions = {}

class Session(object):
	"""Session object to keep track of persistent sessions"""
	def __init__(self, client_id):
		self.client_id = client_id
		self.subscriptions = dict()
		self.undelivered_messages = dict()

	def add_subscription(topic):
		if topic not in subscriptions:
			self.subscriptions[topic] = {'qos1': {}, 'qos2': {}}


def connect_callback(packet):
	clean_session = packet.ConnectFlags #& 1 != 0
	logger.debug('clean_session = ' + str(clean_session))

def publish_callback(packet):
	logger.debug('Sending to clients having port: ' + ' AND '.join(str(c.remote.port) for c in get_clients(packet.Topic)))
	send_to_clients(packet.Topic, packet.build())

def subscribe_callback(client, packet):
	logger.debug('SUBSCRIPTION')
	if packet.Topic in subscriptions:
		if (client,_) in subscriptions[packet.Topic]:
			subscriptions[packet.Topic].remove((client,_))
			subscriptions[packet.Topic].add((client, packet.GrantedQoS))
		else:
			subscriptions[packet.Topic].add((client, packet.GrantedQoS))
	else:
		subscriptions[packet.Topic] = {(client, packet.GrantedQoS)}

def disconnect_callback(packet):
	pass

def get_clients(topic):
	if topic in subscripions:
		return subscriptions[topic]
	else:
		return None

def send_to_clients(topic, packet):
	if topic in subscriptions:
		for client in subscriptions[topic]:
			client.send(packet)
