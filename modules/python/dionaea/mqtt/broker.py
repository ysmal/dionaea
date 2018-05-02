import logging
import re

from dionaea.mqtt.include.packets import *
from dionaea.mqtt.include.packets import *

logger = logging.getLogger('mqtt')

subscriptions = {}
sessions = dict()

class Session(object):
	"""Session object to keep track of persistent sessions"""
	def __init__(self, clean_session, client, client_id):
		self.client = client
		self.client_id = client_id
		self.clean_session = clean_session
		self.subscriptions = dict()
		self.undelivered_messages = dict()
		self.last_will = None
		self.username = None
		self.password = None

	def add_subscription(topic):
		if topic not in subscriptions:
			self.subscriptions[topic] = {'qos1': {}, 'qos2': {}}

def connect_callback(client, packet):
	client_id 	  = str(packet.ClientID)
	clean_session = packet.ConnectFlags & 2**2 != 0 # clean_session = TRUE
	#clean_session = packet.ConnectFlags & 2**1 != 0 # clean_session = FALSE
	logger.debug('clean_session = ' + str(clean_session))
	last_will 	  = packet.ConnectFlags & CONNECT_WILL
	username 	  = packet.Username
	password 	  = packet.Password
	session 	  = None

	if clean_session:
		# No session state needs to be cached for this client after disconnection
		if client_id is not None and client_id != "":
			# Specified client_id is valid
			existing_client = existing_client_id(client_id)
			if existing_client:
				# Client already has an existing session
				delete_session(existing_client, client_id)
				session = create_session(True, client, client_id)
			else:
				# Client doesn't have an existing session
				session = create_session(True, client, client_id)
		else:
			# No client_id specified, generates one
			client_id = gen_client_id()
			session = create_session(True, client, client_id)
	else:
		existing_client = existing_client_id(client_id)
		# Client wants a persistent session
		if client_id is None:
			# TODO: Zero-byte client_id or client_id already exist, respond with CONNACK and 
			# return code 0x02 (Identifier rejected) and then close the network connection.
			pass
		elif existing_client is None:
			# Client never establish a session before
			session = create_session(False, client, client_id)
		else:
			# Client already has a session
			sessions[client] = sessions.pop(existing_client)
			session = sessions[client]

	if last_will:
		topic = packet.WillTopic
		message = packet.WillMessage
		session.last_will = (topic, message)

	if username is not None and password is not None:
		session.username = username
		session.password = password

	logger.debug('Sessions: \n' + str(sessions))

def publish_callback(packet):
	#logger.warn('LIST OF SESSIONS :')
	#for key, value in sessions.items():
	#	logger.warn(str(key))
	logger.warn('LIST OF TOPICS :' + str(subscriptions))
	send_to_clients(packet.Topic, packet.build())

def subscribe_callback(client, packet):
	topic = str(packet.Topic)
	# Check valid use of wildcards
	if '#' in topic and not topic.endswith('#'):
	    # [MQTT-4.7.1-2] Wildcard character '#' is only allowed as last character in filter
	    return
	if topic != "+":
	    if '+' in topic:
	        if "/+" not in topic and "+/" not in topic:
	            # [MQTT-4.7.1-3] + wildcard character must occupy entire level
	            return
	if packet.Topic in subscriptions:
		subscriptions[packet.Topic] = {i for i in subscriptions[packet.Topic] if sessions[i[0]].client_id != sessions[client].client_id} #Si client déjà abonné à ce topic, on le retire
		subscriptions[packet.Topic].add((client, packet.GrantedQoS))
	else:
		subscriptions[packet.Topic] = {(client, packet.GrantedQoS)}

def disconnect_callback(client, packet):
	session = sessions[client]
	client_id = session.client_id
	if session.last_will is not None:
		# TODO: Handle last will (topic, message) (Disconnect from the broker cleanly. Using
		# disconnect() will not result in a will message being sent by the broker.)
		#packet = MQTT_Publish(data)
		#send_to_clients(topic, packet)
		pass
	if session.clean_session:
		# Must delete the state for this client
		delete_session(client, client_id)
	logger.debug('Sessions: \n' + str(sessions))

#def get_clients(topic):
#	if topic in subscriptions:
#		return [i[0] for i in subscriptions[topic]]			#Crée une liste des premiers éléments des tuples
#	else:
#		return None

def send_to_clients(topic, packet):
	if topic in subscriptions:
		for client in subscriptions[topic]:
			client[0].send(packet)

def create_session(clean_session, client, client_id):
	new_session = Session(clean_session, client, client_id)
	sessions[client] = new_session
	return new_session

def delete_session(client, client_id):
	# TODO: Delete subscriptions
	# logger.debug("Deleting session %s subscriptions" % repr(session.client_id))

	# Delete session
	del sessions[client]

def existing_client_id(client_id):
	for k, v in sessions.items():
		if v.client_id == client_id:
			return k
	return None

def matches(topic, a_filter):
        if "#" not in a_filter and "+" not in a_filter:
            # if filter doesn't contain wildcard, return exact match
            return a_filter == topic
        else:
            # else use regex
            match_pattern = re.compile(a_filter.replace('#', '.*').replace('$', '\$').replace('+', '[/\$\s\w\d]+'))
            return match_pattern.match(topic)