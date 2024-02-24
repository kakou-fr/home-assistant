import paho.mqtt.client as mqtt
import os
import time
import serial
import sys
import configparser

sys.stdout = open('/var/log/x2ddaemon.log', 'a', buffering=1)
sys.stderr = sys.stdout


config = configparser.ConfigParser()
config.read('/etc/X2Ddaemon.conf')
# Configuration MQTT
MQTT_BROKER = config['MQTT']['broker']
MQTT_PORT = int(config['MQTT']['port'])  # Convertir en entier
MQTT_TOPIC = config['MQTT']['topic']
MQTT_CLIENT_ID = config['MQTT']['client_id']
MQTT_USERNAME = config['MQTT']['username']
MQTT_PASSWORD = config['MQTT']['password']

# Configuration du port série USB
USB_DEVICE = "/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0"
BAUDRATE = 9600

# Dictionnaire pour stocker les derniers messages de chaque zone
last_messages = {
    "zone1": "",
    "zone2": "",
    "zone3": ""
}

# Ouvrir le port série USB
usb_handle = serial.Serial(USB_DEVICE, BAUDRATE)

# Fonction pour lire les derniers ordres depuis les fichiers de log de chaque zone
def read_last_orders():
    for zone in last_messages.keys():
        log_file = f"zone{zone[4:]}.log"
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                lines = f.readlines()
                if lines:
                    last_order = lines[-1].strip()
                    last_order = last_order.split(' - ')[-1]
                    #last_messages[zone] = f"{last_order}{zone[4:]}"
                    #write_and_print_usb_data(f"{last_order}{zone[4:]}",f"{zone[4:]}")
                    write_and_print_usb_data(f"{last_order}",f"{zone[4:]}")
                else:
                    # Si le fichier est vide, envoyer "OffX" sur le port USB
                    write_and_print_usb_data(f"Off{zone[4:]}",f"{zone[4:]}")
        else:
            # Si le fichier n'existe pas, envoyer "OffX" sur le port USB
            write_and_print_usb_data(f"Off{zone[4:]}",f"{zone[4:]}")

# Callback lors de la réception d'un message MQTT
def on_message(client, userdata, msg):
    print("===> MQTT\n")
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    zone = topic.split('/')[-1]  # Extraire le numéro de la zone à partir du sujet MQTT
   
    # Écrire le message sur le périphérique USB avec l'ordre concaténé à la zone
    write_and_print_usb_data(f"{payload}{zone[4:]}",f"{zone[4:]}")
    
    # Mettre à jour le dernier message de la zone
    last_messages[f"zone{zone[4:]}"] = f"{payload}{zone[4:]}"

# Fonction pour lire et afficher ce qui est présent sur le port USB
def read_and_print_usb_data():
    while usb_handle.in_waiting > 0:
        print(usb_handle.read().decode('utf-8'), end='')

# Fonction pour écrire sur le port USB et afficher ce qui est présent sur le port USB
def write_and_print_usb_data(data, zone):
    print("====>"+zone+" : "+data)
    read_and_print_usb_data()
    time.sleep(1)
    usb_handle.write(('N'+data+'\n').encode())
    usb_handle.flush()  # Flush the write buffer
    # Lire et afficher ce qui est présent sur le port USB
    time.sleep(1)
    read_and_print_usb_data()

    print("====>"+zone+" : "+data)
    read_and_print_usb_data()
    time.sleep(1)
    usb_handle.write((data+'\n').encode())
    usb_handle.flush()  # Flush the write buffer
    # Lire et afficher ce qui est présent sur le port USB
    time.sleep(1)
    read_and_print_usb_data()
     
    # Enregistrer l'ordre envoyé dans le fichier de log ordres.log
    with open("ordres.log", "a") as ordres_log:
        ordres_log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {data}\n")
    
    # Enregistrer le message dans le fichier de journal de la zone
    log_file = f"zone{zone}.log"
    with open(log_file, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {data}\n")

# Fonction pour récupérer les valeurs actuelles des topics MQTT
def get_current_orders_from_mqtt():
    for zone in last_messages.keys():
        topic = f"{MQTT_TOPIC}/{zone}"
        client.subscribe(topic)
        client.publish(topic, "")  # Demande la valeur actuelle en publiant un message vide
        time.sleep(0.5)  # Attendre un court instant pour la réception du message
        client.loop(timeout=1)  # Attendre la réception du message
        # Les valeurs seront mises à jour dans la fonction on_message
 

# Afficher le contenu du port usb
time.sleep(5)  # Attente de 5 secondes a la connection
read_and_print_usb_data()
# Configuration du client MQTT
client = mqtt.Client(client_id=MQTT_CLIENT_ID)
client.on_message = on_message
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

# Connexion au broker MQTT
client.connect(MQTT_BROKER, MQTT_PORT)

# Abonnement au topic MQTT pour toutes les zones
client.subscribe(MQTT_TOPIC + "/#")

start_time = time.time()
read_last_orders()
write_and_print_usb_data("Asso1","1")
write_and_print_usb_data("Asso2","2")
write_and_print_usb_data("Asso3","3")
try:
    while True:
        # Lecture des derniers ordres au démarrage
        if time.time() - start_time > 20:
                start_time = time.time()
                read_last_orders()
                #get_current_orders_from_mqtt()
        client.loop(timeout=1)
        
except KeyboardInterrupt:
    pass

# Fermer le port série USB à la fin
usb_handle.close()

# Arrêt du client MQTT
client.disconnect()

