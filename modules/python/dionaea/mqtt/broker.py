import logging
from dionaea.mqtt.include.packets import *

logger = logging.getLogger('mqtt')

subscriptions = {}
sessions = dict()

class Session(object):
	"""Session object to keep track of persistent sessions"""
	def __init__(self, client, client_id):
		self.client = client
		self.client_id = client_id
		self.subscriptions = dict()
		self.undelivered_messages = dict()
		self.last_will = None
		self.username = None
		self.password = None

	def add_subscription(topic):
		if topic not in subscriptions:
			self.subscriptions[topic] = {'qos1': {}, 'qos2': {}}


def connect_callback(client, packet):
	client_id 	  = packet.ClientID
	clean_session = packet.ConnectFlags & 2**1 != 0
	last_will 	  = packet.ConnectFlags & CONNECT_WILL
	username 	  = packet.Username
	password 	  = packet.Password
	session 	  = None

	if clean_session:
		# No session state needs to be cached for this client after disconnection
		if client_id is not None and client_id != "":
			if client_id in sessions:
				# Client already has an existing session
				delete_session(client, client_id)
			else:
				session = create_session(client, client_id)
		else:
			# No client_id specified, generates one
			client_id = gen_client_id()
			session = create_session(client, client_id)
	else:
		# Client wants a persistent session
		if client_id is None:
			# If the client supplies a zero-byte ClientId, the Client MUST also set CleanSession to 1
			# TODO: respond with CONNACK and return code 0x02 (Identifier rejected) and then close the 
			# Network Connection.
			pass
		elif client_id not in sessions:
			# Client never establish a session before
			session = create_session(client, client_id)
		else:
			# Client already has a session, do nothing
			pass

	if last_will:
		topic = packet.WillTopic
		message = packet.WillMessage
		session.last_will = (topic, message)

	if username is not None and password is not None:
		session.username = username
		session.password = password

def publish_callback(packet):
	send_to_clients(packet.Topic, packet.build())

def subscribe_callback(client, packet):
	logger.debug('SUBSCRIPTION')
	if packet.Topic in subscriptions:
		subscriptions[packet.Topic].add(client)
	else:
		subscriptions[packet.Topic] = {client}

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

def create_session(client, client_id):
	new_session = Session(client, client_id)
	sessions[client] = new_session
	return new_session

def delete_session(client, client_id):
	session = sessions[client]

	# TODO: Delete subscriptions
	logger.debug("Deleting session %s subscriptions" % repr(session.client_id))

	# Delete session
	del sessions[client]