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
		
		if len(data) > l:
			p = None
			x = None
			connect 	= False
			publish 	= False
			subscribe 	= False
			unsubscribe = False
			disconnect 	= False
			puback 		= False

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

				logger.info('---> New message received: CONNECT')

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
				logger.info('---> New message received: PUBLISH QoS 1')

				x = MQTT_Publish(data)

				i = incident("dionaea.modules.python.mqtt.publish")
				i.con = self
				i.publishtopic = x.Topic
				i.publishmessage = x.Message
				i.retain = (x.HeaderFlags & 2**0) != 0
				i.qos = (x.HeaderFlags & 0b00000110) >> 1

				# Added
				publish = True

				i.report()

			elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
				((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS2) > 0) ) :
				logger.info('---> New message received: PUBLISH QoS 2')

				x = MQTT_Publish(data)

				i = incident("dionaea.modules.python.mqtt.publish")
				i.con = self
				i.publishtopic = x.Topic
				i.publishmessage = x.Message
				i.retain = (x.HeaderFlags & 2**0) != 0
				i.qos = (x.HeaderFlags & 0b00000110) >> 1

				# Added
				publish = True

				i.report()

			elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL) == 96) &
				((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) > 0) ) :
				logger.info('---> New message received: PUBLISHREL')

				x = MQTT_Publish_Release(data)
				
				puback = True

			elif (((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) & 
				((self.pendingPacketType >> 6) == 0 )):
				logger.info('---> New message received: PUBLISH QoS 0')

				x = MQTT_Publish(data)

				i = incident("dionaea.modules.python.mqtt.publish")
				i.con = self
				i.publishtopic = x.Topic
				i.publishmessage = x.Message
				i.retain = (x.HeaderFlags & 2**0) != 0
				i.qos = (x.HeaderFlags & 0b00000110) >> 1

				# Added
				publish = True

				i.report()

			elif self.pendingPacketType & 240 == MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE:
				x = MQTT_Subscribe(data)

				if x.GrantedQoS == 0:
					logger.info('---> New message received: SUBSCRIBE QoS 0')
				elif x.GrantedQoS == 1:
					logger.info('---> New message received: SUBSCRIBE QoS 1')
				else:
					logger.info('---> New message received: SUBSCRIBE QoS 2')

				i = incident("dionaea.modules.python.mqtt.subscribe")
				i.con = self
				i.subscribemessageid = x.PacketIdentifier
				i.subscribetopic = x.Topic
				i.qos = x.GrantedQoS

				subscribe = True

				i.report()

			elif self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_UNSUBSCRIBE == 162:
				logger.info('---> New message received: UNSUBSCRIBE')

				x = MQTT_Unsubscribe(data)

				# TODO
				# i = incident("dionaea.modules.python.mqtt.unsubscribe")
				# i.con = self
				# i.subscribemessageid = x.PacketIdentifier
				# i.subscribetopic = x.Topic

				unsubscribe = True

				# i.report()

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_PINGREQ:
				logger.info('---> New message received: PINGREQ')

				x = MQTT_PingRequest(data)

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_DISCONNECT:
				logger.info('---> New message received: DISCONNECT')

				x = MQTT_DisconnectReq(data)

				disconnect = True

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_PUBLISHACK:
				logger.info('---> New message received: PUBLISHACK')

				x = MQTT_PublishACK(data)
				
				puback = True

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_PUBLISHRCV:
				logger.info('---> New message received: PUBLISHRCV')

				x = MQTT_Publish_Received(data)
				
				puback = True

			elif self.pendingPacketType == MQTT_CONTROLMESSAGE_TYPE_PUBLISHCOM:
				logger.info('---> New message received: PUBLISHCOM')

				x = MQTT_Publish_Complete(data)

				puback = True

			else:
				logger.info('---> ' + str(self.pendingPacketType) + ' DISCARDED')
				pass

			self.buf = b''

			r = None
			if connect:
				r = connect_callback(self, x)
			elif publish:
				publish_callback(x)
			elif subscribe:
				r = subscribe_callback(self, x)
			elif unsubscribe:
				unsubscribe_callback(self, x)
			elif disconnect:
				disconnect_callback(self, x)
			elif puback:
				puback_callback(self, x)

			if r == 1:
				rp = MQTT_ConnectACK()
				rp.ConnectionACK = 0x01				
				logger.warn('---> Unacceptable protocol version, return code 0x01.')
				rp.show()
				self.send(rp.build())
			elif r == 2:
				rp = MQTT_ConnectACK()
				rp.ConnectionACK = 0x02
				logger.warn('---> Identifier rejected, return code 0x02.')
				rp.show()
				self.send(rp.build())
			elif r == 3:
				# wrong topic filter
				packetidentifier = x.getlayer(MQTT_Subscribe).PacketIdentifier
				rp = MQTT_SubscribeACK_Identifier()
				rp.PacketIdentifier = packetidentifier
				rp.MessageLength = 0x03
				rp.GrantedQoS = 0b10000000
				rp.show()
				self.send(rp.build())
			elif r == 100:
				rp = MQTT_ConnectACK()
				rp.ConnectionACK = 0x100				# Set Session Present Flag	
				rp.show()
				self.send(rp.build())
			elif r == 101:
				rp = MQTT_ConnectACK()
				rp.ConnectionACK = 0x100				# Set Session Present Flag
				rp.show()
				self.send(rp.build())
				# Resend unacknowledged packets
				redeliver_packets(self)
			else:
				rp = self.process(self.pendingPacketType, x)
				if rp:
					rp.show()
					self.send(rp.build())
				
		return len(data)

	def process(self, PacketType, p):
		r =''
		rp = None
		
		if PacketType == MQTT_CONTROLMESSAGE_TYPE_CONNECT:
			logger.debug("CONNECT ACK")
			r = MQTT_ConnectACK()

		elif PacketType == MQTT_CONTROLMESSAGE_TYPE_DISCONNECT:
			r = ''

		elif PacketType == MQTT_CONTROLMESSAGE_TYPE_PINGREQ:
			logger.debug("PINGREQ")
			r = MQTT_PingResponse()

		#elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE) == 128) &
		#	((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) > 0) ) :

		elif PacketType & MQTT_CONTROLMESSAGE_TYPE_UNSUBSCRIBE == 162:
			logger.debug("UNSUBSCRIBE ACK")
			l = p.getlayer(MQTT_Unsubscribe)
			packetidentifier = l.PacketIdentifier
			r = MQTT_UnsubscribeACK_Identifier()
			if (packetidentifier is not None):
				r.PacketIdentifier = packetidentifier

		elif PacketType & MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE == 128:
			logger.debug("SUBSCRIBE ACK")
			l = p.getlayer(MQTT_Subscribe)
			packetidentifier = l.PacketIdentifier
			GrantedQoS = l.GrantedQoS
			r = MQTT_SubscribeACK_Identifier()
			if (packetidentifier is not None):
				r.PacketIdentifier = packetidentifier
				logger.debug('Packet ID SUBACK: ' + str(packetidentifier))
			if (GrantedQoS is not None):
				r.GrantedQoS = GrantedQoS
				r.MessageLength = 0x03					#2 for Packet ID + 1 for QoS

		# mqtt-v3.1.1-os.pdf - page 36
		# For "Publish" Packet, the Response will be varied with the QoS level:
		# - QoS level 0 - No response packet
		# - QoS level 1 - PUBACK packet
		# - QoS level 2 - PUBREC packet
		elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
			((PacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) == 2) ) :
			logger.debug("PUBLISH ACK QOS1")
			l = p.getlayer(MQTT_Publish)
			packetidentifier = l.PacketIdentifier
			if (packetidentifier is not None):
				r = MQTT_PublishACK_Identifier()
				r.PacketIdentifier = packetidentifier

		elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
			((PacketType & MQTT_CONTROLMESSAGE_TYPE_QoS2) == 4) ) :
			logger.debug("PUBLISH RCV")
			l = p.getlayer(MQTT_Publish)
			packetidentifier = l.PacketIdentifier
			if (packetidentifier is not None):
				r = MQTT_Publish_Received()
				r.HeaderFlags = MQTT_CONTROLMESSAGE_TYPE_PUBLISHRCV
				r.PacketIdentifier = packetidentifier
				undelivered_qos2(self, r)

		elif (  ((self.pendingPacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISH) == 48) &
			((PacketType & MQTT_CONTROLMESSAGE_TYPE_QoS1) == 0) ) :
			logger.debug("PUBLISH ACK QOS0")
			r = None

		elif (PacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISHRCV) == 80:
			logger.debug("PUBLISH REL")
			l = p.getlayer(MQTT_Publish_Received)
			packetidentifier = l.PacketIdentifier
			if (packetidentifier is not None):
				r = MQTT_Publish_Release()
				r.PacketIdentifier = packetidentifier
				r.HeaderFlags = (MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL + 2)		#Last 4 bits of header are reserved 0010
				undelivered_qos2(self, r)

		elif (PacketType & MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL) == 96:
			logger.debug("PUBLISH COMP")
			l = p.getlayer(MQTT_Publish_Release)
			packetidentifier = l.PacketIdentifier
			if (packetidentifier is not None):
				r = MQTT_Publish_Complete()
				r.PacketIdentifier = packetidentifier
				r.HeaderFlags = MQTT_CONTROLMESSAGE_TYPE_PUBLISHCOM
		else:
			logger.warn("Unknown Packet Type for MQTT {}".format(PacketType))
		
		return r
	
	def handle_timeout_idle(self):
		return False

	def handle_disconnect(self):
		return False

