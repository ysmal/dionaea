import random

def gen_client_id():
    """
    Generates random client ID
    """
    gen_id = 'clientID'

    for i in range(7, 23):
        gen_id += chr(random.randint(0, 74) + 48)
    return gen_id