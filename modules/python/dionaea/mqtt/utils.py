import random

# Generates random client ID
def gen_client_id():
    gen_id = 'ID'
    for i in range(7, 23):
        gen_id += chr(random.randint(0, 74) + 48)
    return gen_id