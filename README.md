# Mining Process Monitor

Sistema completo per il monitoraggio di processi minerari con IoT, ML e 
notifiche.

## 🚀 Quick Start

1. **Configura le credenziali:**
   ```bash
   # Copia e modifica il file environment
   cp .env.example .env
   # Aggiungi le tue credenziali email e Google Cloud
   
   # Aggiungi il file credentials.json di Google Cloud Firestore
   # nella root del progetto
   ```

2. **Avvia con Docker:**
   ```bash
   docker-compose up -d
   ```

3. **Accedi al sistema:**
   - URL: http://localhost:8080
   - Login: admin/admin123

## 📁 Struttura Progetto

```
mining-monitor/
├── mqtt_client.py              # Client MQTT
├── main.py                     # Server Flask  
├── ml_predictor.py             # Machine Learning
├── email_notifications.py      # Sistema email
├── grafici_mining.py           # Grafici
├── docker-compose.yml          # Orchestrazione
└── templates/                  # Template HTML
```

## ⚙️ Configurazione

1. **Google Firestore:** Metti `credentials.json` nella root
2. **Email SMTP:** Configura `.env` con le credenziali
3. **Dataset:** Il sistema crea dati di esempio automaticamente

## 🔧 Sviluppo

```bash
# Installa dipendenze
pip install -r requirements.txt

# Avvia componenti separatamente
python main.py              # Server Flask
python mqtt_client.py       # Client MQTT
```

## 📊 Funzionalità

- ✅ Simulazione sensori IoT via MQTT
- ✅ Dashboard web con autenticazione
- ✅ Machine Learning per predizioni
- ✅ Sistema allerte email automatiche
- ✅ Grafici interattivi real-time
- ✅ Analisi performance temporali

## 👥 Login Utenti Demo

- admin/admin123 (Amministratore)
- operator/op123 (Operatore)
- manager/mg123 (Manager)

Progetto per Pervasive Computing e Cloud - Università
