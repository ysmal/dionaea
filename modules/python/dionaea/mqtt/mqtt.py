#********************************************************************************
#*                               Dionaea
#*                           - catches bugs -
#*
#*
#*
#* Copyright (C) 2015  Tan Kean Siong
#* 
#* This program is free software; you can redistribute it and/or
#* modify it under the terms of the GNU General Public License
#* as published by the Free Software Foundation; either version 2
#* of the License, or (at your option) any later version.
#* 
#* This program is distributed in the hope that it will be useful,
#* but WITHOUT ANY WARRANTY; without even the implied warranty of
#* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#* GNU General Public License for more details.
#* 
#* You should have received a copy of the GNU General Public License
#* along with this program; if not, write to the Free Software
#* Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#* 
#* 
#*             contact nepenthesdev@gmail.com  
#*
#*******************************************************************************/

from dionaea.core import *

import datetime
import traceback
import logging
import binascii
import os
import tempfile

from dionaea.mqtt.include.packets import *
from dionaea.mqtt.broker import *

logger = logging.getLogger('mqtt')

clients = []

class mqttd(connection):
	def __init__ (self):
		connection.__init__(self,"tcp")
		self.buf = b''

	def handle_established(self):
		self.timeouts.idle = 120
		self.processors()

	def handle_io_in(self, data):
		l=0
		size = 0
		chunk = b''

		#logger.debug('REMOTE -> ' + str(self.remote.host) + ':' + str(self.remote.port))
		
		if len(data) > l:
			p = None
			x = None
			# Added
			connect = False
			publish = False
			subscribe = False
			disconnect = False
			try:

				if len(data) > 0:
					p = MQTT_ControlMessage_Type(data);
					p.show()

					self.pendingPacketType = p.ControlPacketType
					logger.warn("MQTT Control Packet Type {}".format(self.pendingPacketType))

				if len(data) == 0:
					logger.warn("Bad MQTT Packet, Length = 0")
					
			except:
				t = traceback.format_exc()
				logger.error(t)
				return l
	
			if self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_CONNECT:
				x = MQTT_Connect(data)

				logger.warn('CONNECT MESSAGE RECEIVED')

				logger.debug('\nDATA = ' + str(data) + '\n')

				i = incident("dionaea.modules.python.mqtt.connect")
				i.con = self
				i.clientid = x.ClientID
				i.willtopic = x.WillTopic
				i.willmessage = x.WillMessage
				i.username = x.Username
				i.password = x.Password

				connect = True

				i.report()
				
			elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
				((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) > 0) ) :
				logger.warn('PUBLISH MESSAGE RECEIVED QoS1')

				x = MQTT_Publish(data)

				i = incident("dionaea.modules.python.mqtt.publish")
				i.con = self
				i.publishtopic = x.Topic
				i.publishmessage = x.Message

				# Added
				publish = True

				i.report()

			elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
				((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS2) > 0) ) :
				logger.warn('PUBLISH MESSAGE RECEIVED QoS2')

				x = MQTT_Publish(data)

				i = incident("dionaea.modules.python.mqtt.publish")
				i.con = self
				i.publishtopic = x.Topic
				i.publishmessage = x.Message

				# Added
				publish = True

				i.report()

			elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL) == 96) &
				((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) > 0) ) :
				logger.warn('PUBLISHREL MESSAGE RECEIVED QoS1')

				x = MQTT_Publish_Release(data)

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_PUBLISH:
				logger.warn('PUBLISH MESSAGE RECEIVED')

				x = MQTT_Publish(data)

				i = incident("dionaea.modules.python.mqtt.publish")
				i.con = self
				i.publishtopic = x.Topic
				i.publishmessage = x.Message

				# Added
				publish = True

				i.report()

			elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE) == 128) &
				((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) > 0) ) :
				logger.warn('SUBSCRIBE MESSAGE RECEIVED QoS1')

				x = MQTT_Subscribe(data)

				i = incident("dionaea.modules.python.mqtt.subscribe")
				i.con = self
				i.subscribemessageid = x.PacketIdentifier
				i.subscribetopic = x.Topic

				subscribe = True

				i.report()

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE:
				logger.warn('subscribe MESSAGE RECEIVED')

				x = MQTT_Subscribe(data)

				i = incident("dionaea.modules.python.mqtt.subscribe")
				i.con = self
				i.subscribemessageid = x.PacketIdentifier
				i.subscribetopic = x.Topic

				subscribe = True

				i.report()

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_PINGREQ:
				logger.warn('PINGREQ MESSAGE RECEIVED')

				x = MQTT_PingRequest(data)

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_DISCONNECT:
				logger.warn('DISCONNECT MESSAGE RECEIVED')

				x = MQTT_DisconnectReq(data)

				disconnect = True

			self.buf = b''
			x.show()

			r = None
			r = self.process(self.pendingPacketType, x)

			if r:
				r.show()
				self.send(r.build()) # Send the building each layer of the MQTT packet

			if connect:
				connect_callback(x)
			elif publish:
				publish_callback(x)
			elif subscribe:
				subscribe_callback(self, x)
			elif disconnect:
				disconnect_callback(x)
				
		return len(data)

	def process(self, PacketType, p):
		r =''
		rp = None
		
		if PacketType == MQTT_CONTROLMESSAGE_TYPE_CONNECT:
			r = MQTT_ConnectACK()

		elif PacketType == MQTT_CONTROLMESSAGE_TYPE_DISCONNECT:
			r = ''

		elif PacketType == MQTT_CONTROLMESSAGE_TYPE_PINGREQ:
			r = MQTT_PingResponse()

		elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE) == 128) &
			((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) > 0) ) :

			l = p.getlayer(MQTT_Subscribe)
			packetidentifier = l.PacketIdentifier
			GrantedQoS = l.GrantedQoS
			r = MQTT_SubscribeACK_Identifier()
			if (packetidentifier is not None):
				r.PacketIdentifier = packetidentifier
				# r.PacketIdentifier == 1
			if (GrantedQoS is not None):
				r.GrantedQoS = GrantedQoS
				# r.GrantedQoS == 0

		# mqtt-v3.1.1-os.pdf - page 36
		# For "Publish" Packet, the Response will be varied with the QoS level:
		# - QoS level 0 - No response packet
		# - QoS level 1 - PUBACK packet
		# - QoS level 2 - PUBREC packet

		elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
			((PacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) == 2) ) :
			l = p.getlayer(MQTT_Publish)
			packetidentifier = l.PacketIdentifier
			if (packetidentifier is not None):
				r = MQTT_PublishACK_Identifier()
				r.PacketIdentifier = packetidentifier

		elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
			((PacketType & MQTT_CONTROLMESSAGE_TYPE_QoS2) == 4) ) :
			l = p.getlayer(MQTT_Publish)
			packetidentifier = l.PacketIdentifier
			if (packetidentifier is not None):
				r = MQTT_PublishACK_Identifier()
				r.HeaderFlags = MQTT_CONTROLMESSAGE_TYPE_PUBLISHRCV
				r.PacketIdentifier = packetidentifier

		elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
			((PacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) == 0) ) :
			r = None

		elif (PacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL) == 96:
			l = p.getlayer(MQTT_Publish_Release)
			packetidentifier = l.PacketIdentifier
			if (packetidentifier is not None):
				r = MQTT_PublishACK_Identifier()
				r.PacketIdentifier = packetidentifier
				r.HeaderFlags = MQTT_CONTROLMESSAGE_TYPE_PUBLISHCOM
		else:
			logger.warn("Unknown Packet Type for MQTT {}".format(PacketType))
		
		return r
	
	def handle_timeout_idle(self):
		return False

	def handle_disconnect(self):
		return False

