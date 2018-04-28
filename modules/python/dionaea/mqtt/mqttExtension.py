clients = {}

def save_client(client, topic):
	if topic in clients:
		clients[topic].add(client)
	else:
		clients[topic] = {client}

def get_clients(topic):
	if topic in clients:
		return clients[topic]
	else:
		return None

def send_to_clients(topic, packet):
	if topic in clients:
		for client in clients[topic]:
			client.send(packet)