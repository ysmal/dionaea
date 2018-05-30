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
		self.subscriptions = set()
		self.undelivered_messages = dict()
		self.is_connected = True
		self.hostname = client.local.host
		self.port = client.local.port
		# self.last_will = None
		# self.username = None
		# self.password = None

def connect_callback(client, packet):
	client_id 	  = packet.ClientID.decode("utf-8")
	#clean_session = packet.ConnectFlags & 2**2 != 0 # clean_session = TRUE
	clean_session = (packet.ConnectFlags & 2**1) != 0 # clean_session = FALSE
	# last_will	  = packet.ConnectFlags & CONNECT_WILL
	username 	  = packet.Username.decode("utf-8")
	password 	  = packet.Password.decode("utf-8")
	session 	  = None

	logger.info("Client ID: " + client_id)
	logger.info('Clean session: ' + str(clean_session))
	logger.info("Username: " + username)
	logger.info("Password: " + password)

	existing_client = existing_client_id(client_id)

	if clean_session:
		# No session state needs to be cached for this client after disconnection
		if client_id is None or client_id == "":
			# No client_id specified, generates one
			logger.info('---> Client ID not specified.')
			client_id = gen_client_id()
			session = create_session(True, client, client_id)
		elif existing_client:
			# Client already has an existing session
			logger.info('---> Client has an ID and already established a session before.')
			delete_session(existing_client, client_id)
			session = create_session(True, client, client_id)
		else:
			# Client doesn't have an existing session
			logger.info('---> Client has an ID but never established a session before.')
			session = create_session(True, client, client_id)
	else:
		# Client wants a persistent session
		if client_id is None or client_id == "":
			# Zero-byte client_id, respond with CONNACK and return code 0x02
			# (Identifier rejected) and then close the network connection.
			logger.info('---> Client ID not specified. Not allowed for a persistent session.')
			logger.info('---> Returning ConnectionACK with a code Ox02.')
			r = MQTT_ConnectACK()
			r.ConnectionACK = 0x02
			return r
		elif existing_client is None:
			# Client never established a session before
			logger.info('---> Client never established a session before.')
			session = create_session(False, client, client_id)
		elif not sessions[existing_client].is_connected:
			# A client already has this client_id in a saved session
			logger.info('---> A client already has this client_id in a saved session.')
			if client.local.host == sessions[existing_client].hostname:
				# Same IP, so should be a client takeover
				logger.info('---> Client already established a persistent session before (same IP: ' 
					+ client.local.host + '). Session resumed.')
				sessions[client] = sessions.pop(existing_client)
				session = sessions[client]
				# Replace client in subscriptions
				replace_client_in_subscriptions(existing_client, client)
			else:
				# Return code 0x02 (Identifier rejected) and then close the network connection.
				logger.info('---> Another client already has this client ID in a saved session.')
				logger.info('---> Returning ConnectionACK with a code Ox02.')
				r = MQTT_ConnectACK()
				r.ConnectionACK = 0x02
				return r
		else:
			# existing_client is connected
			if client.local.host == sessions[existing_client].hostname:
				# Same IP, so should be a client takeover
				logger.info('---> Client takeover as the previous client (same IP: ' + client.local.host 
					+ ') with this ID didnt disconnect gracefully.')
				sessions[client] = sessions.pop(existing_client)
				session = sessions[client]
				# Replace client in subscriptions
				replace_client_in_subscriptions(existing_client, client)
			else:
				# A connected client already has this client_id currently, return code
				# 0x02 (Identifier rejected) and then close the network connection.
				logger.info('---> Another client already have this client ID in a current session.')
				logger.info('---> Returning ConnectionACK with a code Ox02.')
				r = MQTT_ConnectACK()
				r.ConnectionACK = 0x02
	return None

	# TODO
	# if last_will:
	# 	topic = packet.WillTopic.decode("utf-8")
	# 	message = packet.WillMessage.decode("utf-8")
	# 	session.last_will = (topic, message)

	# TODO
	# if username is not None and password is not None:
	# 	session.username = username.decode("utf-8")
	# 	session.password = password.decode("utf-8")

	logger.info('---> Sessions stored in the broker: \n' + str(sessions))

def publish_callback(packet):
	topic 		   = packet.Topic.decode("utf-8")
	message  	   = packet.Message.decode("utf-8")
	retained 	   = (packet.HeaderFlags & 2**0) != 0
	qos 		   = packet.HeaderFlags & 0b00000110

	logger.info('Topic: ' + topic)
	logger.info('Message: ' + message)
	logger.info('Retained: ' + str(retained))
	logger.info('QoS: ' + str(qos))

	if retained:
		if len(message) == 0 or message is None:
			delete_retained_message(topic)
		else:
			add_retained_message(topic, packet, qos)

	for a_filter, v in subscriptions.items():
		if matches(topic, a_filter):
			send_to_clients(a_filter, packet)

def subscribe_callback(client, packet):
	topic = packet.Topic.decode("utf-8")
	granted_qos = packet.GrantedQoS

	logger.info('Topic: ' + topic)
	logger.info('Granted QoS: ' + str(granted_qos))

	# Check valid use of wildcards
	if not valid_topic(topic):
		logger.info('---> Topic: ' + topic + ' is not valid.')
		return

	add_subscription(topic, client, granted_qos)

	for topic_retained, v in retained_messages.items():
		if matches(topic_retained, topic):
			pending_retained_message = retained_messages[topic_retained]
			if pending_retained_message:
				send(client, pending_retained_message[0])

def unsubscribe_callback(client, packet):
	topic = packet.Topic.decode("utf-8")

	logger.info('Topic: ' + topic)

	# Check valid use of wildcards
	if not valid_topic(topic):
		return

	delete_subscription(topic, client)

def disconnect_callback(client, packet):
	session = sessions[client]
	client_id = session.client_id
	if session.clean_session:
		# Must delete the state for this client
		delete_session(client, client_id)
	else:
		# Keep the client state in memory but indicate that client is disconnected
		session.is_connected = False
	logger.debug('---> Sessions stored in the broker: \n' + str(sessions))


# ----------------------------------------------------------------------------------------------


def valid_topic(topic):
	if '#' in topic and not topic.endswith('#'):
		# Wildcard character '#' is only allowed as last character in filter
		logger.info('---> Topic: ' + topic + ' is not valid.')
		return False
	if topic != "+":
		if '+' in topic:
			if "/+" not in topic and "+/" not in topic:
				# + wildcard character must occupy entire level
				return False
	logger.info('---> Topic: ' + topic + ' is valid.')
	return True

def add_retained_message(topic, packet, qos):
	retained_messages[topic] = (packet, qos)
	logger.info('---> Retained message added for topic ' + topic + ': ' 
		+ str(retained_messages[topic]))

def delete_retained_message(topic):
	if topic in retained_messages:
		del retained_messages[topic]
		logger.info('---> Retained message deleted for topic ' + topic + '.')

def add_subscription(topic, client, qos):
	if topic in subscriptions:
		delete_subscription(topic, client)
		subscriptions[topic].add((client, qos))
	else:
		subscriptions[topic] = {(client, qos)}
	# Save subscription in client state
	sessions[client].subscriptions.add(topic)
	logger.info('---> Added subscription: ' + topic + ' for client ' 
		+ sessions[client].client_id)

def delete_subscription(topic, client):
	if topic not in subscriptions:
		return
	subscriptions[topic] = {i for i in subscriptions[topic]
	if sessions[i[0]].client_id != sessions[client].client_id}
	# Delete subscription in client state
	if topic in sessions[client].subscriptions:
		sessions[client].subscriptions.remove(topic)
		logger.info('---> Deleted subscription: ' + topic + ' for client ' 
		+ sessions[client].client_id)

def send_to_clients(topic, packet):
	if topic in subscriptions:
		for client in subscriptions[topic]:
			send(client[0], packet)

def send(client, packet):
	if sessions[client].is_connected:
		client.send(packet.build())
		logger.info('---> Packet sent :' +  str(packet) + ' to client: ' 
			+ sessions[client].client_id)

def create_session(clean_session, client, client_id):
	new_session = Session(clean_session, client, client_id)
	sessions[client] = new_session
	logger.info('---> Created a new session for client: ' + client_id)
	return new_session

def delete_session(client, client_id):
	# Delete subscriptions
	subs = sessions[client].subscriptions
	for topic in subs:
		delete_subscription(topic, client)
	# Delete session
	del sessions[client]
	logger.info('Deleted session for client: ' + client_id)

def existing_client_id(client_id):
	for k, v in sessions.items():
		if v.client_id == client_id:
			return k
	return None

def replace_client_in_subscriptions(existing_client, client):
	for k, v in subscriptions.items():
		# v is a set
		for t in v:
			if t[0] == existing_client:
				qos = t[1]
				subscriptions[k].remove(t)
				subscriptions[k].add((client, qos))
				logger.info('---> Replaced in subscriptions client: ' + sessions[existing_client].client_id 
					+ ' by client: ' + sessions[client].client_id) + ' for topic: ' + k

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
		topic_pattern = re.compile(topic.replace('#', '.*')
			.replace('$', '\$').replace('+', '[/\$\s\w\d]+'))
		return match_pattern.match(topic)