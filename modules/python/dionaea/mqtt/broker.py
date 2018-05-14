import logging
import re

from dionaea.mqtt.include.packets import *
from dionaea.mqtt.include.packets import *
from dionaea.mqtt.utils import *

logger = logging.getLogger('mqtt')

sessions = dict()

subscriptions = {}
retained_messages = {}

class Session(object):
	"""Session object to keep track of persistent sessions"""
	def __init__(self, clean_session, client, client_id):
		self.client = client
		self.client_id = client_id
		self.clean_session = clean_session
		self.subscriptions = list()
		self.undelivered_messages = dict()
		self.is_connected = True
		# self.last_will = None
		# self.username = None
		# self.password = None

def connect_callback(client, packet):
	client_id 	  = str(packet.ClientID)
	#clean_session = packet.ConnectFlags & 2**2 != 0 # clean_session = TRUE
	clean_session = packet.ConnectFlags & 2**1 != 0 # clean_session = FALSE
	logger.debug('clean_session = ' + str(clean_session))
	# last_will	  = packet.ConnectFlags & CONNECT_WILL
	# username 	  = packet.Username
	# password 	  = packet.Password
	session 	  = None

	existing_client = existing_client_id(client_id)

	if clean_session:
		# No session state needs to be cached for this client after disconnection
		if client_id is None or client_id == "":
			# No client_id specified, generates one
			client_id = gen_client_id()
			session = create_session(True, client, client_id)
		elif existing_client:
			# Client already has an existing session
			delete_session(existing_client, client_id)
			session = create_session(True, client, client_id)
		else:
			# Client doesn't have an existing session
			session = create_session(True, client, client_id)
	else:
		# Client wants a persistent session
		if client_id is None or client_id == "":
			# TODO: Zero-byte client_id, respond with CONNACK and return code 0x02
			# (Identifier rejected) and then close the network connection.
			logger.debug('client_id is None or client_id != ""')
			pass
		elif existing_client is None:
			# Client never establish a session before
			logger.debug('Client never establish a session before')
			session = create_session(False, client, client_id)
		elif sessions[existing_client].is_connected:
			# A client already has this client_id in a saved session
			# TODO: client_id already in use by another client, respond with CONNACK and return
			# code 0x02 (Identifier rejected) and then close the network connection.
			logger.debug('A client already has this client_id in a saved session')
			pass
		else:
			# client_id not in use by another client,
			# should the one from this client.
			logger.debug('client_id existing and not in use by another client')
			sessions[client] = sessions.pop(existing_client)
			session = sessions[client]

	# TODO
	# if last_will:
	# 	topic = packet.WillTopic
	# 	message = packet.WillMessage
	# 	session.last_will = (topic, message)

	# TODO
	# if username is not None and password is not None:
	# 	session.username = username
	# 	session.password = password

	logger.debug('Sessions: \n' + str(sessions))

def publish_callback(packet):
	topic 		   = packet.Topic
	message  	   = packet.Message
	retained 	   = packet.HeaderFlags & 2**0 != 0
	logger.debug('retained == ' + str(retained))
	qos 		   = packet.HeaderFlags & 0b00000110
	logger.debug('qos == ' + str(qos))

	if retained:
		if len(message) == 0 or message is None:
			delete_retained_message(topic)
		else:
			add_retained_message(topic, packet, qos)

	for a_filter, v in subscriptions.items():
		if matches(topic, a_filter):
			send_to_clients(a_filter, packet)

def subscribe_callback(client, packet):
	topic = str(packet.Topic)

	# Check valid use of wildcards
	if not valid_topic(topic):
		return

	add_subscription(packet.Topic, client, packet.GrantedQoS)

	for topic_retained, v in retained_messages.items():
		if matches(topic_retained, topic):
			logger.debug('SUBSCRIBE: matches(topic_retained, topic)')
			pending_retained_message = retained_messages[topic_retained]
			if pending_retained_message:
				send(client, pending_retained_message[0])
		else:
			logger.debug('SUBSCRIBE: NOT matches(topic, a_filter): ' 
				+ str(topic_retained) + ' and ' + str(topic))

def disconnect_callback(client, packet):
	session = sessions[client]
	client_id = session.client_id
	if session.clean_session:
		# Must delete the state for this client
		delete_session(client, client_id)
	else:
		# Keep the client state in memory but indicate that client is disconnected
		session.is_connected = False
	logger.debug('Sessions: \n' + str(sessions))


# ----------------------------------------------------------------------------------------------


def valid_topic(topic):
	if '#' in topic and not topic.endswith('#'):
		# Wildcard character '#' is only allowed as last character in filter
		return False
	if topic != "+":
		if '+' in topic:
			if "/+" not in topic and "+/" not in topic:
				# + wildcard character must occupy entire level
				return False
	return True

def add_retained_message(topic, packet, qos):
	retained_messages[topic] = (packet, qos)
	logger.debug('added retained message for topic ' + str(topic) + ': ' 
		+ str(retained_messages[topic]))

def delete_retained_message(topic):
	if topic in retained_messages:
		logger.debug('deleting retained message for topic ' + str(topic))
		del retained_messages[topic]

def add_subscription(topic, client, qos):
	if topic in subscriptions:
		delete_subscription(topic, client)
		subscriptions[topic].add((client, qos))
	else:
		subscriptions[topic] = {(client, qos)}
	# Save subscription in client state
	sessions[client].subscriptions.append(topic)
	logger.debug('Subscriptions for client ' + str(client) + ': ' 
		+ str(sessions[client].subscriptions))

def delete_subscription(topic, client):
	subscriptions[topic] = {i for i in subscriptions[topic] 
	if sessions[i[0]].client_id != sessions[client].client_id}

def send_to_clients(topic, packet):
	if topic in subscriptions:
		for client in subscriptions[topic]:
			send(client[0], packet)

def send(client, packet):
	logger.debug('Sending packet to client ' + str(client))
	client.send(packet.build())

def create_session(clean_session, client, client_id):
	new_session = Session(clean_session, client, client_id)
	sessions[client] = new_session
	return new_session

def delete_session(client, client_id):
	# Delete subscriptions
	subs = sessions[client].subscriptions
	for topic in subs:
		delete_subscription(topic, client)
	# Delete session
	del sessions[client]

def existing_client_id(client_id):
	for k, v in sessions.items():
		if v.client_id == client_id:
			return k
	return None

def matches(topic, a_filter):
	topic = str(topic)
	a_filter = str(a_filter)
	if "#" not in a_filter and "+" not in a_filter:
		# if filter doesn't contain wildcard, return exact match
		return a_filter == topic
	else:
		# else use regex
		match_pattern = re.compile(a_filter.replace('#', '.*')
			.replace('$', '\$').replace('+', '[/\$\s\w\d]+'))
		return match_pattern.match(topic)