import logging

logger = logging.getLogger('mqtt')

clients = {}

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
	if packet.Topic in clients:
		clients[packet.Topic].add(client)
	else:
		clients[packet.Topic] = {client}

def disconnect_callback(packet):
	pass

def get_clients(topic):
	if topic in clients:
		return clients[topic]
	else:
		return None

def send_to_clients(topic, packet):
	if topic in clients:
		for client in clients[topic]:
			client.send(packet)
