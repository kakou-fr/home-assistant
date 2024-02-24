import paho.mqtt.client as mqtt
import os
import time
import serial
import sys
import configparser
import datetime
import subprocess

sys.stdout = open('/var/log/X2Ddaemon/x2ddaemon.log', 'a', buffering=1)
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

LOG_DIR = "/var/log/X2Ddaemon/"
ORDERS_LOG_FILE = os.path.join(LOG_DIR, "ordres.log")
MQTT_LOG_FILE = os.path.join(LOG_DIR, "mqtt.log")

# Ouvrir le port série USB
usb_handle = serial.Serial(USB_DEVICE, BAUDRATE)

def printlog(message):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def log_mqtt_order(order):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(MQTT_LOG_FILE, "a") as mqtt_log:
        mqtt_log.write(f"{timestamp} - {order}\n")

def publish_current_state_to_mqtt(client):
    for zone, state in last_messages.items():
        topic = f"radiateurs/zones_actuel/zone{zone[4:]}"
        payload = f"{state}"
        payload = payload[:-1]
        if payload:
            client.publish(topic, payload, retain=True)

# Fonction pour lire les derniers ordres depuis les fichiers de log de chaque zone
def read_last_orders():
    for zone in last_messages.keys():
        log_file = os.path.join(LOG_DIR, f"zone{zone[4:]}.log")
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

def flush_mqtt_messages(client):
    # Attendre jusqu'à ce que tous les messages MQTT en attente soient envoyés
    time.sleep(5)
    # Déconnexion propre du client MQTT
    client.disconnect()

# Callback lors de la réception d'un message MQTT
def on_message(client, userdata, msg):
    start_time = time.time()
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    printlog("===> MQTT : "+topic+" = "+payload+"\n")

    if "restart" in payload:
        print("Received restart command. Exiting program.")
        client.publish("radiateurs/etat", "unavailable", retain=True)
        client.publish("radiateurs/ordre", "done", retain=True)
        flush_mqtt_messages(client)
        print("Restart now")
        os._exit(0)  # Quitter le programme immédiatement
    if "reboot" in payload:
        print("Received reboot command. Rebooting the machine.")
        client.publish("radiateurs/etat", "unavailable", retain=True)
        client.publish("radiateurs/ordre", "done", retain=True)
        flush_mqtt_messages(client)
        subprocess.run(["sudo", "reboot"])  # Redémarrer la machine

    zone = topic.split('/')[-1]  # Extraire le numéro de la zone à partir du sujet MQTT
    order = f"{payload}{zone[4:]}"   

    valid_zones = ['zone1', 'zone2', 'zone3']
    if zone not in valid_zones:
        print(f"Ignoring message for invalid zone: {zone}")
        return

    # Vérifier si l'ordre est valide (Sun, Moon, Hg, Off, On ou Asso)
    valid_orders = ['Sun', 'Moon', 'Hg', 'Off', 'On', 'Asso']
    if payload not in valid_orders:
        print(f"Ignoring message with invalid order: {payload}")
        return

    # Écrire le message sur le périphérique USB avec l'ordre concaténé à la zone
    write_and_print_usb_data(order,f"{zone[4:]}")
    
    # Mettre à jour le dernier message de la zone
    last_messages[f"zone{zone[4:]}"] = order
    log_mqtt_order(order)

# Fonction pour lire et afficher ce qui est présent sur le port USB
def read_and_print_usb_data():
    while usb_handle.in_waiting > 0:
        print(usb_handle.read().decode('utf-8'), end='')

def read_and_print_usb_data_mqtt():
    if usb_handle.in_waiting > 0:
        while usb_handle.in_waiting > 0:
            data = usb_handle.read().decode('utf-8')
            print(data, end='')
        # Publier l'état d'émission dans "radiateurs/etat" avec retain
        client.publish("radiateurs/etat", "ok", retain=True)
    else:
        printlog("unavailable")
        # Publier "unavailable" dans "radiateurs/etat" avec retain
        client.publish("radiateurs/etat", "unavailable", retain=True)

# Fonction pour écrire sur le port USB et afficher ce qui est présent sur le port USB
def write_and_print_usb_data(data, zone, save_to_logs=True):
    # Publier l'état actuel en MQTT après chaque envoi d'ordre
    if save_to_logs:
        publish_current_state_to_mqtt(client)
    printlog("====>"+zone+" : "+data)
    read_and_print_usb_data()
    time.sleep(1)
    usb_handle.write(('N'+data+'\n').encode())
    usb_handle.flush()  # Flush the write buffer
    # Lire et afficher ce qui est présent sur le port USB
    time.sleep(1)
    read_and_print_usb_data()

    printlog("====>"+zone+" : "+data)
    read_and_print_usb_data()
    time.sleep(1)
    usb_handle.write((data+'\n').encode())
    usb_handle.flush()  # Flush the write buffer
    # Lire et afficher ce qui est présent sur le port USB
    time.sleep(1)
    read_and_print_usb_data_mqtt()
    if save_to_logs:    
        # Enregistrer l'ordre envoyé dans le fichier de log ordres.log
        with open(ORDERS_LOG_FILE, "a") as ordres_log:
            ordres_log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {data}\n")
    
        # Enregistrer le message dans le fichier de journal de la zone
        log_file = os.path.join(LOG_DIR, f"zone{zone}.log")
        with open(log_file, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {data}\n")

# Afficher le contenu du port usb
time.sleep(5)  # Attente de 5 secondes a la connection
read_and_print_usb_data()
# Configuration du client MQTT
client = mqtt.Client(client_id=MQTT_CLIENT_ID)
client.on_message = on_message
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

# Connexion au broker MQTT
client.connect(MQTT_BROKER, MQTT_PORT)

# Publier "on" dans "radiateurs/etat" au démarrage avec retain
client.publish("radiateurs/etat", "on", retain=True)
client.publish("radiateurs/ordre", "on", retain=True)

# Abonnement au topic MQTT pour toutes les zones
client.subscribe("radiateurs/ordre")
client.subscribe(MQTT_TOPIC + "/#")

start_time = time.time()
write_and_print_usb_data("Asso1","1", False)
write_and_print_usb_data("Asso2","2", False)
write_and_print_usb_data("Asso3","3", False)
read_last_orders()

publish_current_state_to_mqtt(client)
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

