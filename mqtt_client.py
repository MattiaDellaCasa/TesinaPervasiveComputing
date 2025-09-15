import pandas as pd
import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime
import argparse

class MiningDataClient:
    def __init__(self, mqtt_broker="localhost", mqtt_port=1883, data_file="data/mining_data.csv"):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.data_file = data_file
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        
        #carica il dataset
        self.df = pd.read_csv(data_file)
        print(f"Dataset caricato: {len(self.df)} righe")
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connesso al broker MQTT {self.mqtt_broker}:{self.mqtt_port}")
        else:
            print(f"Errore connessione MQTT: {rc}")
    
    def on_publish(self, client, userdata, mid):
        print(f"Messaggio pubblicato: {mid}")
    
    def connect_mqtt(self):
        #connessione a MQTT
        try:
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"Errore connessione MQTT: {e}")
            return False
    
    def send_data_row(self, row_index):
        #invia riga
        if row_index >= len(self.df):
            return False
        
        row = self.df.iloc[row_index]
        
        #prepara il messaggio
        message = {
            'timestamp': datetime.now().isoformat(),
            'row_index': row_index,
            'data': row.to_dict()
        }
        
        #converti valori
        for key, value in message['data'].items():
            if pd.isna(value):
                message['data'][key] = None
            elif hasattr(value, 'item'):
                message['data'][key] = value.item()
        
        #pubblica su MQTT
        topic = "mining/sensor_data"
        payload = json.dumps(message)
        
        try:
            result = self.client.publish(topic, payload)
            if result.rc == 0:
                silica_val = row.get('% Silica Concentrate', 'N/A')
                if pd.notna(silica_val):
                    print(f"Inviata riga {row_index}: % Silica Concentrate = {silica_val:.2f}")
                else:
                    print(f"Inviata riga {row_index}")
                return True
            else:
                print(f"Errore invio riga {row_index}: {result.rc}")
                return False
        except Exception as e:
            print(f"Errore invio dati: {e}")
            return False
    
    def start_streaming(self, interval=20, start_row=0, max_rows=None):
        #avvia streamin dati
        if not self.connect_mqtt():
            return
        
        print(f"Avvio streaming dati ogni {interval} secondi...")
        print(f"Dataset: {len(self.df)} righe totali")
        
        row_index = start_row
        end_row = min(len(self.df), start_row + max_rows) if max_rows else len(self.df)
        
        try:
            while row_index < end_row:
                success = self.send_data_row(row_index)
                if success:
                    row_index += 1
                
                time.sleep(interval)
            
            print(f"Streaming completato. Inviate {row_index - start_row} righe.")
            
        except KeyboardInterrupt:
            print("\nStreaming interrotto dall'utente")
        except Exception as e:
            print(f"Errore durante lo streaming: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    parser = argparse.ArgumentParser(description='Client MQTT per dati minerari')
    parser.add_argument('--broker', default='localhost', help='Indirizzo broker MQTT')
    parser.add_argument('--port', type=int, default=1883, help='Porta broker MQTT')
    parser.add_argument('--file', default='data/mining_data.csv', help='File CSV dei dati')
    parser.add_argument('--interval', type=int, default=20, help='Intervallo in secondi tra gli invii')
    parser.add_argument('--start', type=int, default=0, help='Riga di inizio')
    parser.add_argument('--max', type=int, help='Numero massimo di righe da inviare')
    
    args = parser.parse_args()
    
    client = MiningDataClient(args.broker, args.port, args.file)
    client.start_streaming(args.interval, args.start, args.max)

if __name__ == "__main__":
    main()
