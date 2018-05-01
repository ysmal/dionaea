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
	logger.debug('packet.ConnectFlags = ' + str(packet.ConnectFlags))
	clean_session = packet.ConnectFlags & 2**1 != 0
	logger.debug('clean_session = ' + str(clean_session))

def publish_callback(packet):
	logger.warn('LIST OF TOPICS :' + str(subscriptions))
	send_to_clients(packet.Topic, packet.build())

def subscribe_callback(client, packet):
	if packet.Topic in subscriptions:
		#subscriptions[packet.Topic] = [i for i in subscriptions[packet.Topic] if (i[0].remote.host == client.remote.host and i[0].remote.port == client.remote.port)] #Si client déjà abonné à ce topic, on le retire
		subscriptions[packet.Topic].add((client, packet.GrantedQoS))
	else:
		subscriptions[packet.Topic] = {(client, packet.GrantedQoS)}

def disconnect_callback(packet):
	pass

#def get_clients(topic):
#	if topic in subscriptions:
#		return [i[0] for i in subscriptions[topic]]			#Crée une liste des premiers éléments des tuples
#	else:
#		return None

def send_to_clients(topic, packet):
	if topic in subscriptions:
		for client in subscriptions[topic]:
			client[0].send(packet)
