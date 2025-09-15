#!/bin/bash

# =================================================================
# 🏭 MINING MONITOR - LAUNCHER AGGIORNATO
# =================================================================
# Avvia automaticamente server Flask + client MQTT
# Doppio click per eseguire!
# =================================================================

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Banner di avvio
echo "=================================================================="
echo -e "${PURPLE}🏭 MINING MONITOR - SISTEMA COMPLETO${NC}"
echo "=================================================================="
echo -e "${GREEN}🚀 Avvio server Flask + client MQTT...${NC}"
echo ""

# Percorso del progetto
PROJECT_PATH="$HOME/Desktop/progetto-mining/mining-monitor"

# Verifica che la cartella esista
if [ ! -d "$PROJECT_PATH" ]; then
    echo -e "${RED}❌ ERRORE: Cartella progetto non trovata!${NC}"
    echo -e "${YELLOW}📁 Percorso cercato: $PROJECT_PATH${NC}"
    echo ""
    echo "Soluzioni possibili:"
    echo "1. Verifica che il progetto sia in ~/Desktop/progetto-mining/mining-monitor"
    echo "2. Oppure modifica il percorso in questo script"
    echo ""
    echo "Premi INVIO per uscire..."
    read
    exit 1
fi

# Vai nella cartella del progetto
cd "$PROJECT_PATH"
echo -e "${BLUE}📁 Posizione: $(pwd)${NC}"

# Verifica che i file necessari esistano
if [ ! -f "main.py" ] || [ ! -f "mqtt_client.py" ]; then
    echo -e "${RED}❌ ERRORE: File mancanti (main.py o mqtt_client.py)${NC}"
    echo "Assicurati che tutti i file siano presenti nella cartella del progetto."
    echo ""
    echo "Premi INVIO per uscire..."
    read
    exit 1
fi

# Verifica che il dataset esista
if [ ! -f "data/mining_data.csv" ]; then
    echo -e "${YELLOW}⚠️  Dataset mining_data.csv non trovato in data/${NC}"
    echo "Il sistema userà dati di esempio se il file non viene trovato."
fi

# Controlla se Python3 è installato
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ ERRORE: Python3 non trovato!${NC}"
    echo "Installa Python3 da: https://www.python.org/downloads/"
    echo ""
    echo "Premi INVIO per uscire..."
    read
    exit 1
fi

# Verifica versione Python
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}🐍 Python: $PYTHON_VERSION${NC}"

# Installa dipendenze se necessarie
echo -e "${YELLOW}🔍 Verifica dipendenze...${NC}"
MISSING_DEPS=""
python3 -c "import flask" 2>/dev/null || MISSING_DEPS="$MISSING_DEPS flask"
python3 -c "import pandas" 2>/dev/null || MISSING_DEPS="$MISSING_DEPS pandas"  
python3 -c "import paho.mqtt.client" 2>/dev/null || MISSING_DEPS="$MISSING_DEPS paho-mqtt"
python3 -c "import plotly" 2>/dev/null || MISSING_DEPS="$MISSING_DEPS plotly"
python3 -c "import sklearn" 2>/dev/null || MISSING_DEPS="$MISSING_DEPS scikit-learn"

if [ ! -z "$MISSING_DEPS" ]; then
    echo -e "${YELLOW}⚠️  Installazione dipendenze mancanti:$MISSING_DEPS${NC}"
    pip3 install flask flask-login pandas paho-mqtt plotly scikit-learn numpy python-dateutil
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Dipendenze installate con successo!${NC}"
    else
        echo -e "${RED}❌ Errore installazione dipendenze${NC}"
        echo "Prova manualmente: pip3 install flask flask-login pandas paho-mqtt plotly scikit-learn numpy"
        echo ""
        echo "Premi INVIO per uscire..."
        read
        exit 1
    fi
else
    echo -e "${GREEN}✅ Tutte le dipendenze sono installate${NC}"
fi

# Verifica Firestore (opzionale)
python3 -c "import google.cloud.firestore" 2>/dev/null && FIRESTORE_OK=true || FIRESTORE_OK=false
if [ "$FIRESTORE_OK" = false ]; then
    echo -e "${YELLOW}⚠️  Google Cloud Firestore non installato (opzionale)${NC}"
    echo "Il sistema funzionerà con dati di esempio se non configurato"
fi

# Termina processi esistenti
echo -e "${YELLOW}🔄 Pulizia processi precedenti...${NC}"
pkill -f "python3 main.py" 2>/dev/null
pkill -f "python3 mqtt_client.py" 2>/dev/null
lsof -ti:8080 | xargs kill -9 2>/dev/null
sleep 2

# Crea cartella logs se non esiste
mkdir -p logs

echo ""
echo "=================================================================="
echo -e "${GREEN}🚀 AVVIO SISTEMA MINING MONITOR${NC}"
echo "=================================================================="
echo -e "${BLUE}🖥️  Server Web: http://localhost:8080${NC}"
echo -e "${BLUE}👤 Login: admin/admin123${NC}"
echo -e "${BLUE}📡 MQTT: Dati ogni 20 secondi${NC}"
echo -e "${YELLOW}🔄 Per fermare: Ctrl+C in questo terminale${NC}"
echo "=================================================================="

# Countdown
for i in 3 2 1; do
    echo -e "${YELLOW}Avvio in $i...${NC}"
    sleep 1
done

echo -e "${GREEN}🎬 SISTEMA IN AVVIO...${NC}"
echo ""

# Funzione per cleanup quando si esce
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Fermando tutti i processi...${NC}"
    kill $SERVER_PID 2>/dev/null
    kill $CLIENT_PID 2>/dev/null
    pkill -f "python3 main.py" 2>/dev/null
    pkill -f "python3 mqtt_client.py" 2>/dev/null
    echo -e "${GREEN}✅ Sistema fermato correttamente${NC}"
    echo ""
    echo "Premi INVIO per chiudere questa finestra..."
    read
    exit 0
}

# Intercetta Ctrl+C
trap cleanup SIGINT SIGTERM

# Avvia server Flask in background
echo -e "${BLUE}🖥️  Avvio server Flask...${NC}"
python3 main.py > logs/server.log 2>&1 &
SERVER_PID=$!

# Aspetta che il server si avvii
echo "Attesa avvio server..."
sleep 8

# Verifica che il server sia attivo
if ! curl -s http://localhost:8080 > /dev/null; then
    echo -e "${RED}❌ Errore avvio server Flask${NC}"
    echo "Controlla logs/server.log per dettagli:"
    echo "---"
    tail -10 logs/server.log
    echo "---"
    kill $SERVER_PID 2>/dev/null
    echo "Premi INVIO per uscire..."
    read
    exit 1
fi

echo -e "${GREEN}✅ Server Flask avviato (PID: $SERVER_PID)${NC}"

# Chiedi all'utente l'intervallo per il client MQTT
echo ""
echo -e "${BLUE}📡 CONFIGURAZIONE CLIENT MQTT${NC}"
echo -e "${BLUE}Default Intervallo: 20 sec${NC}"
echo -ne "${BLUE}Per impostare un valore differente digitalo qui: ${NC}"
read user_interval

# Valida l'input dell'utente
if [ -z "$user_interval" ]; then
    MQTT_INTERVAL=20
    echo -e "${BLUE}✅ Usando intervallo default: 20 secondi${NC}"
elif [[ "$user_interval" =~ ^[0-9]+$ ]] && [ "$user_interval" -gt 0 ]; then
    MQTT_INTERVAL=$user_interval
    echo -e "${BLUE}✅ Intervallo impostato a: $MQTT_INTERVAL secondi${NC}"
else
    echo -e "${YELLOW}⚠️  Valore non valido, usando default: 20 secondi${NC}"
    MQTT_INTERVAL=20
fi

# Avvia client MQTT in background con l'intervallo scelto
echo -e "${BLUE}📡 Avvio client MQTT (intervallo: ${MQTT_INTERVAL}s)...${NC}"
python3 mqtt_client.py --broker localhost --interval $MQTT_INTERVAL > logs/client.log 2>&1 &
CLIENT_PID=$!

echo -e "${GREEN}✅ Client MQTT avviato (PID: $CLIENT_PID)${NC}"

# Apri browser automaticamente
echo -e "${BLUE}🌐 Apertura browser...${NC}"
(sleep 3 && open http://localhost:8080/login) &

echo ""
echo "=================================================================="
echo -e "${GREEN}🎉 SISTEMA OPERATIVO!${NC}"
echo "=================================================================="
echo -e "${BLUE}🌐 Dashboard: http://localhost:8080${NC}"
echo -e "${BLUE}📊 Dati MQTT: Ogni $MQTT_INTERVAL secondi${NC}"
echo -e "${BLUE}📁 Log server: logs/server.log${NC}"
echo -e "${BLUE}📁 Log client: logs/client.log${NC}"
echo -e "${BLUE}💾 Database: Firestore (se configurato)${NC}"
echo ""
echo -e "${YELLOW}Il sistema invia dati automaticamente ogni $MQTT_INTERVAL secondi${NC}"
echo -e "${YELLOW}I grafici si aggiornano automaticamente${NC}"
echo -e "${YELLOW}Premi Ctrl+C per fermare tutto${NC}"
echo "=================================================================="

# Monitora i processi e mostra status
while true; do
    # Verifica che i processi siano ancora attivi
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo -e "${RED}❌ Server Flask crashato! Controlla logs/server.log${NC}"
        break
    fi
    
    if ! kill -0 $CLIENT_PID 2>/dev/null; then
        echo -e "${RED}❌ Client MQTT crashato! Controlla logs/client.log${NC}"
        echo -e "${YELLOW}⚠️  Riavvio client MQTT (intervallo: ${MQTT_INTERVAL}s)...${NC}"
        python3 mqtt_client.py --broker localhost --interval $MQTT_INTERVAL > logs/client.log 2>&1 &
        CLIENT_PID=$!
        echo -e "${GREEN}✅ Client MQTT riavviato (PID: $CLIENT_PID)${NC}"
    fi
    
    sleep 10
done

cleanup
