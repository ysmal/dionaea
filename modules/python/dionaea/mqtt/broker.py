import logging
import re
import queue
import itertools
import time
import datetime

from collections import deque

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
		self.undelivered_messages = deque()
		self.is_connected = True
		self.hostname = client.local.host
		self.port = client.local.port

def connect_callback(client, packet):
	protocol 	  = packet.ProtocolName.decode("utf-8")
	client_id 	  = packet.ClientID.decode("utf-8")
	clean_session = (packet.ConnectFlags & 0b00000010) >> 1
	username 	  = packet.Username.decode("utf-8")
	password 	  = packet.Password.decode("utf-8")
	session 	  = None

	if (protocol != "MQTT"):
		return 1

	logger.info("Client ID: " + client_id)
	logger.info('Clean session: ' + str(clean_session))
	logger.info("Username: " + username)
	logger.info("Password: " + password)

	existing_client = existing_client_id(client_id)

	if clean_session:
		# No session state needs to be cached for this client after disconnection
		if client_id is None or client_id == "":
			if not clean_session:			# No client_id specified must have clean session = True
				return 2
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
			return 2
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
				sessions[client].is_connected = True
				session = sessions[client]
				# Replace client in subscriptions
				replace_client_in_subscriptions(existing_client, client)
				return 101
			else:
				# Return code 0x02 (Identifier rejected) and then close the network connection.
				logger.info('---> Another client already has this client ID in a saved session.')
				logger.info('---> Returning ConnectionACK with a code Ox02.')
				return 2
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

				return 100
			else:
				# A connected client already has this client_id currently, return code
				# 0x02 (Identifier rejected) and then close the network connection.
				logger.info('---> Another client already have this client ID in a current session.')
				logger.info('---> Returning ConnectionACK with a code Ox02.')
				return 2
	return None

	logger.info('---> Sessions stored in the broker: \n' + str(sessions))

def publish_callback(packet):
	topic 		   = packet.Topic.decode("utf-8")
	message  	   = packet.Message.decode("utf-8")
	retained 	   = (packet.HeaderFlags & 2**0) != 0
	qos 		   = (packet.HeaderFlags & 0b00000110) >> 1
	header         = packet.HeaderFlags
 
	logger.info('Topic: ' + topic)
	logger.info('Message: ' + message)
	logger.info('Retained: ' + str(retained))
	logger.info('QoS: ' + str(qos))
	logger.info('Header: ' + str(header))

	if retained:
		if len(message) == 0 or message is None:
			delete_retained_message(topic)
		else:
			add_retained_message(topic, packet, qos)

	for a_filter, v in subscriptions.items():
		if matches(topic, a_filter):
			send_to_clients(a_filter, packet, qos)

def puback_callback(client, packet):
	if not sessions[client].clean_session:
		packet_id = packet.PacketIdentifier
		ptype = packet.HeaderFlags & 0xF0
		acknowledge_publish(client, packet_id, ptype)

def subscribe_callback(client, packet):
	topic = packet.Topic.decode("utf-8")
	granted_qos = packet.GrantedQoS
	packet_id = packet.PacketIdentifier

	logger.info('Topic: ' + topic)
	logger.info('Granted QoS: ' + str(granted_qos))
	logger.info('Packet ID: ' + str(packet_id))

	# Check valid use of wildcards
	if not valid_topic(topic) or granted_qos > 2:
		logger.info('---> Topic: ' + topic + ' is not valid.')
		return 3

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

def redeliver_packets(client):
	for undelivered in sessions[client].undelivered_messages:
		send(client, undelivered[1])
		time.sleep(0.5)

def add_retained_message(topic, packet, qos):
	retained_messages[topic] = (packet, qos)
	logger.info('---> Retained message added for topic ' + topic + ': ' 
		+ str(retained_messages[topic]))

def delete_retained_message(topic):
	if topic in retained_messages:
		del retained_messages[topic]

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

def send_to_clients(topic, packet, qos):
	if topic in subscriptions:
		for client in subscriptions[topic]:
			p = copy.deepcopy(packet)
			p = process_qos(client[0], p, qos, client[1])
			send(client[0], p)

def send(client, packet):
	if sessions[client].is_connected:
		client.send(packet.build())
		logger.info('---> Packet sent :' +  str(packet) + ' to client: ' 
			+ sessions[client].client_id)

def process_qos(client, packet, qos1, qos2):
	if qos1 > qos2:
		qos = qos2
		if qos2 == 0:					#No Packet ID field if qos=0
			packet.MessageLength = packet.MessageLength - 2
		packet.HeaderFlags = ((packet.HeaderFlags & 0b11111001) | (qos2 << 1))
	else:
		qos = qos1

	if not qos == 0 and not sessions[client].clean_session :
		if sessions[client].undelivered_messages:
			undelivered_ids = [undelivered[0] for undelivered in sessions[client].undelivered_messages]
			if packet.PacketIdentifier in undelivered_ids:
				for i in itertools.count():
					if not i in undelivered_ids:
						packet.PacketIdentifier = i
						break
		sessions[client].undelivered_messages.append((packet.PacketIdentifier, packet))

	return packet

def acknowledge_publish(client, packet_id, ptype):
	new_queue = deque()

	while sessions[client].undelivered_messages:
		elem = sessions[client].undelivered_messages.popleft()
		if elem[0] == packet_id:
			if ptype == 0x40:			#PUBACK
				if elem[1].HeaderFlags == 0x32:			#PUB QoS1
					continue
			elif ptype == 0x50:			#PUBREC
				if elem[1].HeaderFlags == 0x34:			#PUB QoS2
					continue
			elif ptype == 0x60:			#PUBREL
				if elem[1].HeaderFlags & 0xF0 == 0x50:			#PUBREC
					continue
			elif ptype == 0x70:			#PUBCOMP
				if elem[1].HeaderFlags & 0xF0 == 0x60:			#PUB REL
					continue
		new_queue.append(elem)

	sessions[client].undelivered_messages = None
	sessions[client].undelivered_messages = new_queue

def undelivered_qos2(client, packet):
	if not sessions[client].clean_session:
		sessions[client].undelivered_messages.append((packet.PacketIdentifier, packet))

def create_session(clean_session, client, client_id):
	new_session = Session(clean_session, client, client_id)
	sessions[client] = new_session
	logger.info('---> Created a new session for client: ' + client_id)
	return new_session

def delete_session(client, client_id):
	# Delete subscriptions
	subs = set(sessions[client].subscriptions)
	for topic in subs:
		delete_subscription(topic, client)
	# Delete session
	del sessions[client]
	logger.info('---> Deleted session for client: ' + client_id)

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

def matches(topic, a_filter):
	topic = str(topic)
	a_filter = str(a_filter)
	if "#" not in a_filter and "+" not in a_filter:
		# if filter doesn't contain wildcard, return exact match
		return a_filter == topic
	elif ('#' == a_filter or a_filter.startswith('+')) and '$SYS' in topic:
		return False
	else:
		# else use regex
		match_pattern = re.compile(a_filter.replace('#', '.*')
			.replace('$', '\$').replace('+', '[/\$\s\w\d]+'))
		topic_pattern = re.compile(topic.replace('#', '.*')
			.replace('$', '\$').replace('+', '[/\$\s\w\d]+'))
		return match_pattern.match(topic)

def get_sub():
	return subscriptions