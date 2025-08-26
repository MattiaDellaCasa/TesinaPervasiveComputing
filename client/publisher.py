# client/publisher.py
import os
import json
import time
from google.cloud import pubsub_v1
from google.auth.exceptions import DefaultCredentialsError
import zipfile
import pandas as pd

# --- CONFIGURAZIONE ---
PROJECT_ID = "tesinapervasivecloud"  # Sostituisci col tuo Project ID
TOPIC_ID = "mining-data"
CREDENTIALS_PATH = r"C:\Users\utente\Documents\TesinaPervasiveComputing\tesinapervasivecloud-2add42c1f190.json"

# Imposta la variabile d'ambiente per le credenziali
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

# --- CLIENT PUB/SUB ---
try:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
except DefaultCredentialsError as e:
    print("❌ Errore credenziali: assicurati che il file JSON esista e sia corretto.")
    print(e)
    exit(1)

# --- FUNZIONE PUBBLICA MESSAGGIO ---
def publish_message(payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        future = publisher.publish(topic_path, data=data)
        ack_id = future.result()
        print("✅ Pubblicato:", payload, "| ack:", ack_id)
    except Exception as e:
        print("❌ Errore durante la pubblicazione:", e)

# --- ESEMPIO DI UTILIZZO ---
if __name__ == "__main__":
    import zipfile
import pandas as pd
# Nome del file zip
zip_filename = "DB.zip"
# Nome del file CSV dentro lo zip
csv_filename = "DB.csv"
# Apri il file zip e leggi il CSV
with zipfile.ZipFile(zip_filename, "r") as z:
    with z.open(csv_filename) as f:
        df = pd.read_csv(f)  # Carica in un DataFrame pandas
        print(df.head())     # Mostra le prime righe
    print(df.head)
    for i in range(5):
        msg = {"id": i, "value": i * 10, "note": "ciao dal client"}
        publish_message(msg)
        time.sleep(2)
