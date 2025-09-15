from flask import Flask, redirect, url_for, request, render_template, jsonify, flash
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
import paho.mqtt.client as mqtt
import json
import threading
import time
from datetime import datetime, timedelta
import os

# Import moduli personalizzati
try:
    import grafici_mining
    import ml_predictor
    import email_notifications
except ImportError as e:
    print(f"Errore import moduli: {e}")

# Setup Firestore (opzionale)
try:
    from google.cloud import firestore
    from google.cloud.firestore_v1 import FieldFilter
    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False
    print("Google Cloud Firestore non disponibile")

class User(UserMixin):
    def __init__(self, username, email=None):
        super().__init__()
        self.id = username
        self.username = username
        self.email = email

class MiningServer:
    def __init__(self):
        self.app = Flask(__name__, template_folder="templates", static_folder="static")
        self.app.config['SECRET_KEY'] = 'mining_secret_key_2024'
        
        # Setup Flask-Login
        self.login = LoginManager(self.app)
        self.login.login_view = 'login_page'
        self.login.user_loader(self.load_user)
        
        # Database utenti
        self.users_db = {
            'admin': {'password': 'admin123', 'email': 'admin@mining.com'},
            'operator': {'password': 'op123', 'email': 'operator@mining.com'},
            'manager': {'password': 'mg123', 'email': 'manager@mining.com'}
        }
        
        # NUOVE IMPOSTAZIONI SETTINGS
        self.settings_file = 'config/settings.json'
        self.settings = {
            'threshold': 4.0,
            'email': {
                'enabled': True,
                'recipients': [],
                'frequency': 'immediate'
            },
            'last_update': None
        }
        self.load_settings()
        
        # Setup Firestore
        if HAS_FIRESTORE:
            try:
                self.db = firestore.Client.from_service_account_json('credentials.json')
                print("Connesso a Firestore")
                
                # AUTO-PULIZIA: Elimina dati vecchi all'avvio
                self.clear_old_data()
                
            except Exception as e:
                print(f"Errore connessione Firestore: {e}")
                self.db = None
        else:
            self.db = None
        
        # Setup MQTT
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.setup_mqtt()
        
        # Setup ML Predictor (VERSIONE AGGIORNATA)
        try:
            # Passa la connessione Firestore al predictor
            self.predictor = ml_predictor.SilicaPredictor(db=self.db)
            
            # Usa la soglia dalle settings
            self.prediction_threshold = self.settings['threshold']
            
            # Stampa info sul modello
            model_info = self.predictor.get_model_info()
            print(f"ML Predictor Status: {model_info['status']}")
            if model_info['status'] == 'READY':
                print(f"Modello: {model_info['model_name']}")
                print(f"R² Score: {model_info['metrics'].get('r2_score', 'N/A')}")
                print(f"Dati training: {model_info['metrics'].get('training_samples', 'N/A')} campioni")
                print(f"Fonte dati: {model_info['metrics'].get('data_source', 'N/A')}")
            
        except Exception as e:
            self.predictor = None
            self.prediction_threshold = self.settings['threshold']
            print(f"ML Predictor non disponibile: {e}")
        
        # Setup Email Notifications
        try:
            self.email_notifier = email_notifications.EmailNotifier()
        except:
            self.email_notifier = None
            print("Email Notifier non disponibile")
        
        # Setup routes
        self.setup_routes()
        
        # Avvia MQTT in thread separato
        self.mqtt_thread = threading.Thread(target=self.start_mqtt_loop, daemon=True)
        self.mqtt_thread.start()
    
    def load_user(self, username):
        if username in self.users_db:
            user_data = self.users_db[username]
            return User(username, user_data.get('email'))
        return None
    
    def load_settings(self):
        """Carica settings dal file JSON"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
                print(f"Settings caricati: soglia={self.settings['threshold']}")
        except Exception as e:
            print(f"Errore caricamento settings: {e}")
    
    def save_settings(self):
        """Salva settings nel file JSON"""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2, default=str)
            print(f"Settings salvati: soglia={self.settings['threshold']}")
        except Exception as e:
            print(f"Errore salvataggio settings: {e}")
    
    def clear_old_data(self):
        """Pulisce automaticamente i dati più vecchi di 1 ora"""
        if not self.db:
            return
        
        try:
            # Calcola il tempo limite (1 ora fa)
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            try:
                from google.cloud.firestore_v1 import FieldFilter
                docs = self.db.collection('mining_data').where(filter=FieldFilter('created_at', '<', cutoff_time)).stream()
            except ImportError:
            # Fallback alla sintassi vecchia se FieldFilter non è disponibile
                docs = self.db.collection('mining_data').where('created_at', '<', cutoff_time).stream()
                
            deleted_count = 0
            for doc in docs:
                doc.reference.delete()
                deleted_count += 1
            
            if deleted_count > 0:
                print(f"Eliminati {deleted_count} documenti vecchi da Firestore")
            else:
                print("Nessun dato vecchio da eliminare")
                
        except Exception as e:
            print(f"Errore durante la pulizia automatica: {e}")
    
    def clear_all_data(self):
        """ATTENZIONE: Elimina TUTTI i dati da Firestore"""
        if not self.db:
            return
        
        try:
            docs = self.db.collection('mining_data').stream()
            deleted_count = 0
            
            for doc in docs:
                doc.reference.delete()
                deleted_count += 1
            
            print(f"Eliminati TUTTI i {deleted_count} documenti da Firestore")
            
        except Exception as e:
            print(f"Errore durante la pulizia completa: {e}")
    
    def setup_mqtt(self):
        """Configura il client MQTT"""
        try:
            mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
            mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
            self.mqtt_client.connect(mqtt_broker, mqtt_port, 60)
            print(f"Client MQTT configurato per {mqtt_broker}:{mqtt_port}")
        except Exception as e:
            print(f"Errore configurazione MQTT: {e}")
    
    def start_mqtt_loop(self):
        """Avvia il loop MQTT in background"""
        self.mqtt_client.loop_forever()
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connesso al broker MQTT")
            client.subscribe("mining/sensor_data")
        else:
            print(f"Errore connessione MQTT: {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """Gestisce i messaggi MQTT ricevuti"""
        try:
            data = json.loads(msg.payload.decode())
            print(f"Ricevuti dati: riga {data.get('row_index', 'N/A')}")
            
            # Salva nel database
            if self.db:
                self.save_to_firestore(data)
            
            # Fai predizione usando la soglia attuale
            if self.predictor:
                sensor_data = data['data']
                prediction = self.predictor.predict_silica(sensor_data)
                
                current_threshold = self.settings['threshold']
                if prediction and prediction > current_threshold:
                    print(f"ALLERTA: Predizione Silica = {prediction:.2f}% (soglia:{current_threshold}%)")
                    if self.email_notifier and self.settings['email']['enabled']:
                        self.send_alert_email(prediction, sensor_data)
            
        except Exception as e:
            print(f"Errore elaborazione messaggio MQTT: {e}")
    
    def save_to_firestore(self, data):
        """Salva i dati su Firestore"""
        try:
            doc_ref = self.db.collection('mining_data').document()
            doc_data = {
                'timestamp': data['timestamp'],
                'row_index': data['row_index'],
                'sensor_data': data['data'],
                'created_at': firestore.SERVER_TIMESTAMP
            }
            doc_ref.set(doc_data)
        except Exception as e:
            print(f"Errore salvataggio Firestore: {e}")
    
    def send_alert_email(self, prediction, sensor_data):
        """Invia email di allerta"""
        if not self.email_notifier:
            return
        
        # Usa i destinatari dalle settings se disponibili
        email_recipients = self.settings['email'].get('recipients', [])
        if not email_recipients:
            # Fallback ai destinatari dal database utenti
            email_recipients = [user_data.get('email') for user_data in self.users_db.values() if user_data.get('email')]
        
        current_threshold = self.settings['threshold']
        subject = f"ALLERTA MINING: Silica sopra soglia ({prediction:.2f}%)"
        
        self.email_notifier.send_alert_email(email_recipients, prediction, current_threshold, sensor_data)
    
    def setup_routes(self):
        """Configura le route Flask"""
        
        @self.app.route('/')
        def home():
            return render_template('base.html')
        
        @self.app.route('/login', methods=['GET', 'POST'])
        def login_page():
            if request.method == 'POST':
                username = request.form['username']
                password = request.form['password']
                next_page = request.form.get('next', '/dashboard')
                
                if username in self.users_db and self.users_db[username]['password'] == password:
                    user = User(username, self.users_db[username].get('email'))
                    login_user(user)
                    return redirect(next_page)
                else:
                    flash('Username o password non corretti')
            
            return render_template('login.html')
        
        @self.app.route('/logout')
        @login_required
        def logout():
            logout_user()
            return redirect('/')
        
        @self.app.route('/dashboard')
        @login_required
        def dashboard():
            return render_template('dashboard.html', username=current_user.username)
        
        @self.app.route('/charts')
        @login_required
        def charts_page():
            return render_template('charts.html')
        
        @self.app.route('/predictions')
        @login_required
        def predictions_page():
            return render_template('predictions.html')
        
        @self.app.route('/settings')
        @login_required
        def settings_page():
            return render_template('settings.html', threshold=self.settings['threshold'])
        
        # API Routes esistenti
        @self.app.route('/api/charts/realtime')
        @login_required
        def realtime_chart():
            """Grafici in tempo reale"""
            try:
                chart_data = grafici_mining.create_realtime_charts(self.db)
                return jsonify(chart_data)
            except Exception as e:
                print(f"Errore API realtime: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/charts/historical')
        @login_required
        def historical_chart():
            """Grafici storici"""
            try:
                chart_data = grafici_mining.create_historical_charts(self.db)
                return jsonify(chart_data)
            except Exception as e:
                print(f"Errore API historical: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/charts/prediction')
        @login_required
        def prediction_chart():
            """Grafici predizioni"""
            try:
                hours_ahead = request.args.get('hours', 1, type=int)
                chart_data = grafici_mining.create_prediction_charts(self.db, self.predictor, hours_ahead)
                return jsonify(chart_data)
            except Exception as e:
                print(f"Errore API prediction: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/charts/raw-data')
        @login_required
        def raw_chart_data():
            """Dati grezzi per i grafici dei parametri"""
            try:
                chart_data = grafici_mining.get_raw_data_for_charts(self.db)
                return jsonify(chart_data)
            except Exception as e:
                print(f"Errore API raw-data: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/prediction/performance')
        @login_required
        def prediction_performance():
            """Performance del modello di predizione"""
            try:
                if self.predictor:
                    performance_data = self.predictor.evaluate_performance_by_time_gap()
                    return jsonify(performance_data)
                else:
                    return jsonify({'error': 'Predictor non disponibile'}), 500
            except Exception as e:
                print(f"Errore API performance: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/model/info')
        @login_required
        def model_info():
            """Informazioni sul modello ML"""
            try:
                if self.predictor:
                    info = self.predictor.get_model_info()
                    return jsonify(info)
                else:
                    return jsonify({'status': 'NOT_AVAILABLE'}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        # NUOVE API SETTINGS INTEGRATE
        @self.app.route('/api/settings/threshold', methods=['GET', 'POST'])
        @login_required
        def threshold_settings():
            """Gestisce la soglia di allerta"""
            if request.method == 'POST':
                try:
                    data = request.get_json()
                    new_threshold = float(data.get('threshold', self.settings['threshold']))
                    
                    if new_threshold < 0 or new_threshold > 10:
                        return jsonify({'success': False, 'error': 'Soglia deve essere tra 0 e 10'})
                    
                    # Aggiorna settings
                    self.settings['threshold'] = new_threshold
                    self.settings['last_update'] = datetime.now().isoformat()
                    self.save_settings()
                    
                    # Aggiorna anche la soglia interna del predictor
                    self.prediction_threshold = new_threshold
                    
                    # Aggiorna la soglia nel modulo grafici se disponibile
                    try:
                        import grafici_mining
                        if hasattr(grafici_mining, 'set_alert_threshold'):
                            grafici_mining.set_alert_threshold(new_threshold)
                    except:
                        pass
                    
                    return jsonify({
                        'success': True, 
                        'threshold': new_threshold,
                        'message': f'Soglia aggiornata a {new_threshold}%'
                    })
                    
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)})
            
            # GET request
            return jsonify({'threshold': self.settings['threshold']})
        
        @self.app.route('/api/settings/email', methods=['POST'])
        @login_required
        def update_email_settings():
            """Aggiorna configurazione email"""
            try:
                data = request.get_json()
                
                email_config = {
                    'enabled': data.get('enabled', True),
                    'recipients': [r.strip() for r in data.get('recipients', '').split(',') if r.strip()],
                    'frequency': data.get('frequency', 'immediate')
                }
                
                self.settings['email'] = email_config
                self.settings['last_update'] = datetime.now().isoformat()
                self.save_settings()
                
                return jsonify({
                    'success': True,
                    'email_config': email_config,
                    'message': 'Configurazione email salvata'
                })
                
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/settings/current', methods=['GET'])
        @login_required
        def get_current_settings():
            """Restituisce configurazione attuale"""
            try:
                return jsonify({
                    'threshold': self.settings.get('threshold', 4.0),
                    'email': self.settings.get('email', {}),
                    'last_update': self.settings.get('last_update'),
                    'success': True
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/settings/threshold-preview', methods=['GET'])
        @login_required
        def threshold_preview():
            """Anteprima impatto nuova soglia"""
            try:
                threshold = float(request.args.get('threshold', 4.0))
                
                # Ottieni dati recenti per calcolare impatto
                if not self.db:
                    return jsonify({
                        'threshold': threshold,
                        'affected_samples': 0,
                        'total_samples': 0,
                        'percentage': 0,
                        'success': True,
                        'warning': 'Database non disponibile'
                    })
                
                try:
                    import grafici_mining
                    df = grafici_mining.get_data_from_firestore(self.db, limit=100)
                    
                    if df is not None and '% Silica Concentrate' in df.columns:
                        affected_samples = int((df['% Silica Concentrate'] > threshold).sum())
                        total_samples = len(df)
                        percentage = (affected_samples / total_samples * 100) if total_samples > 0 else 0
                        
                        return jsonify({
                            'threshold': threshold,
                            'affected_samples': affected_samples,
                            'total_samples': total_samples,
                            'percentage': round(percentage, 1),
                            'success': True
                        })
                    else:
                        return jsonify({
                            'threshold': threshold,
                            'affected_samples': 0,
                            'total_samples': 0,
                            'percentage': 0,
                            'success': True,
                            'warning': 'Nessun dato disponibile per preview'
                        })
                except Exception as e:
                    return jsonify({
                        'threshold': threshold,
                        'affected_samples': 0,
                        'total_samples': 0,
                        'percentage': 0,
                        'success': True,
                        'warning': f'Errore nel calcolo preview: {str(e)}'
                    })
                    
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/settings/statistics', methods=['GET'])
        @login_required
        def get_alert_statistics():
            """Statistiche allerte e sistema"""
            try:
                if not self.db:
                    return jsonify({
                        'recent_alerts': 0,
                        'alerts_today': 0,
                        'alerts_week': 0,
                        'avg_silica': 0,
                        'total_samples': 0,
                        'alert_percentage': 0,
                        'success': True,
                        'warning': 'Database non disponibile'
                    })
                
                try:
                    import grafici_mining
                    df = grafici_mining.get_data_from_firestore(self.db, limit=1000)
                    
                    if df is None or df.empty:
                        return jsonify({
                            'recent_alerts': 0,
                            'alerts_today': 0,
                            'alerts_week': 0,
                            'avg_silica': 0,
                            'total_samples': 0,
                            'alert_percentage': 0,
                            'success': True,
                            'warning': 'Nessun dato disponibile'
                        })
                    
                    current_threshold = self.settings.get('threshold', 4.0)
                    
                    # Calcola statistiche
                    total_samples = len(df)
                    total_alerts = int((df['% Silica Concentrate'] > current_threshold).sum())
                    alert_percentage = (total_alerts / total_samples * 100) if total_samples > 0 else 0
                    avg_silica = float(df['% Silica Concentrate'].mean())
                    
                    # Simula allerte per oggi e settimana (sostituisci con logica reale basata su timestamp)
                    alerts_today = min(total_alerts, max(0, int(total_alerts * 0.1)))  # 10% delle allerte oggi
                    alerts_week = min(total_alerts, max(alerts_today, int(total_alerts * 0.3)))  # 30% questa settimana
                    
                    # Allerte recenti (ultimi 100 campioni)
                    recent_df = df.tail(100)
                    recent_alerts = int((recent_df['% Silica Concentrate'] > current_threshold).sum())
                    
                    return jsonify({
                        'recent_alerts': recent_alerts,
                        'alerts_today': alerts_today,
                        'alerts_week': alerts_week,
                        'avg_silica': round(avg_silica, 2),
                        'total_samples': total_samples,
                        'alert_percentage': round(alert_percentage, 1),
                        'current_threshold': current_threshold,
                        'success': True
                    })
                    
                except Exception as e:
                    return jsonify({
                        'recent_alerts': 0,
                        'alerts_today': 0,
                        'alerts_week': 0,
                        'avg_silica': 0,
                        'total_samples': 0,
                        'alert_percentage': 0,
                        'success': True,
                        'error': f'Errore nel calcolo statistiche: {str(e)}'
                    })
                    
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/admin/clear-data', methods=['POST'])
        @login_required
        def clear_data():
            """Route per eliminare tutti i dati (solo admin)"""
            if current_user.username != 'admin':
                return jsonify({'error': 'Accesso negato'}), 403
            
            try:
                self.clear_all_data()
                return jsonify({'success': True, 'message': 'Dati eliminati con successo'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/admin/retrain-model', methods=['POST'])
        @login_required
        def retrain_model():
            """Route per riallenare il modello manualmente (solo admin)"""
            if current_user.username != 'admin':
                return jsonify({'error': 'Accesso negato'}), 403
            
            try:
                if self.predictor:
                    success = self.predictor.train_model()
                    if success:
                        info = self.predictor.get_model_info()
                        return jsonify({
                            'success': True, 
                            'message': 'Modello riaddestrato con successo',
                            'model_info': info
                        })
                    else:
                        return jsonify({'error': 'Errore durante il riaddestramento'}), 500
                else:
                    return jsonify({'error': 'Predictor non disponibile'}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/settings/test-email', methods=['POST'])
        @login_required
        def test_email():
            """Invia email di test"""
            try:
                data = request.get_json()
                recipients = data.get('recipients', [])
                
                if not recipients:
                    return jsonify({'success': False, 'error': 'Nessun destinatario specificato'})
                
                if not self.email_notifier:
                    return jsonify({'success': False, 'error': 'Servizio email non configurato'})
                
                # Invia email di test
                subject = "Test Email - Sistema Mining"
                message = f"""
                <h2>Email di Test - Sistema Mining</h2>
                <p>Questo è un messaggio di test per verificare che le notifiche email funzionino correttamente.</p>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Utente:</strong> {current_user.username}</p>
                <p>Se ricevi questo messaggio, la configurazione email è corretta.</p>
                <hr>
                <small>Sistema di Monitoraggio Mining - Test Automatico</small>
                """
                
                sent_count = 0
                for recipient in recipients:
                    if self.email_notifier.send_email(recipient, subject, message, is_html=True):
                        sent_count += 1
                
                return jsonify({
                    'success': True,
                    'sent_count': sent_count,
                    'total_recipients': len(recipients),
                    'message': f'Email di test inviata a {sent_count}/{len(recipients)} destinatari'
                })
                
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/notifications/send-prediction-alert', methods=['POST'])
        @login_required
        def send_prediction_alert():
            """Invia notifica per allerte predizioni"""
            try:
                data = request.get_json()
                
                prediction_period = data.get('prediction_period', 'prossimo periodo')
                alerts_count = data.get('alerts_count', 0)
                threshold = data.get('threshold', 4.0)
                max_prediction = data.get('max_prediction', 0)
                avg_prediction = data.get('avg_prediction', 0)
                prediction_horizon = data.get('prediction_horizon', 'N/A')
                
                # Ottieni destinatari dalle impostazioni
                email_recipients = self.settings['email'].get('recipients', [])
                
                if not email_recipients:
                    return jsonify({'success': False, 'error': 'Nessun destinatario email configurato'})
                
                if not self.email_notifier:
                    return jsonify({'success': False, 'error': 'Servizio email non configurato'})
                
                if not self.settings['email'].get('enabled', False):
                    return jsonify({'success': False, 'error': 'Notifiche email disabilitate'})
                
                # Prepara messaggio email
                subject = f"🚨 ALLERTA PREDIZIONI: {alerts_count} allerte nel {prediction_period}"
                
                html_message = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; }}
                        .alert {{ background-color: #fff3cd; border: 1px solid #ffeaa7; 
                                  padding: 20px; border-radius: 5px; border-left: 4px solid #ffc107; }}
                        .header {{ color: #856404; font-size: 24px; font-weight: bold; }}
                        .critical {{ color: #dc3545; font-weight: bold; }}
                        .stats {{ background-color: #f8f9fa; padding: 15px; border-radius: 3px; margin: 10px 0; }}
                        .footer {{ margin-top: 20px; padding-top: 15px; border-top: 1px solid #ddd; 
                                   font-size: 12px; color: #666; }}
                    </style>
                </head>
                <body>
                    <div class="alert">
                        <div class="header">⚠️ ALLERTA PREDIZIONI MINING</div>
                        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p class="critical">Nel {prediction_period} sono previste <strong>{alerts_count} allerte</strong> per percentuale silica superiore alla soglia di <strong>{threshold}%</strong></p>
                        
                        <div class="stats">
                            <h4>Dettagli Predizioni:</h4>
                            <ul>
                                <li><strong>Massimo predetto:</strong> {max_prediction:.2f}% Silica</li>
                                <li><strong>Media predetta:</strong> {avg_prediction:.2f}% Silica</li>
                                <li><strong>Orizzonte temporale:</strong> {prediction_horizon}</li>
                                <li><strong>Soglia configurata:</strong> {threshold}%</li>
                                <li><strong>Allerte previste:</strong> {alerts_count}</li>
                            </ul>
                        </div>
                        
                        <p><strong>🎯 Azione raccomandata:</strong> Monitorare attentamente il processo nelle prossime ore e verificare i parametri di flotazione se necessario.</p>
                        
                        <div class="footer">
                            <p>Notifica generata automaticamente dal Sistema di Monitoraggio Mining<br>
                            Utente: <strong>{current_user.username}</strong> | 
                            Sistema: <strong>Predizioni ML</strong></p>
                        </div>
                    </div>
                </body>
                </html>
                """
                
                text_message = f"""
                ALLERTA PREDIZIONI MINING
                ========================
                
                Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                
                Nel {prediction_period} sono previste {alerts_count} allerte
                per percentuale silica superiore alla soglia di {threshold}%
                
                DETTAGLI PREDIZIONI:
                - Massimo predetto: {max_prediction:.2f}% Silica
                - Media predetta: {avg_prediction:.2f}% Silica
                - Orizzonte temporale: {prediction_horizon}
                - Soglia configurata: {threshold}%
                - Allerte previste: {alerts_count}
                
                AZIONE RACCOMANDATA: 
                Monitorare attentamente il processo nelle prossime ore
                e verificare i parametri di flotazione se necessario.
                
                Sistema di Monitoraggio Mining
                Utente: {current_user.username}
                """
                
                # Invia email
                sent_count = 0
                if isinstance(email_recipients, str):
                    email_recipients = [r.strip() for r in email_recipients.split(',') if r.strip()]
                
                for recipient in email_recipients:
                    if recipient:
                        if self.email_notifier.send_email(recipient, subject, html_message, is_html=True):
                            sent_count += 1
                        elif self.email_notifier.send_email(recipient, subject, text_message, is_html=False):
                            sent_count += 1
                
                return jsonify({
                    'success': True,
                    'recipients_count': sent_count,
                    'total_recipients': len(email_recipients),
                    'message': f'Notifica allerta inviata a {sent_count} destinatari',
                    'alerts_count': alerts_count,
                    'prediction_period': prediction_period
                })
                
            except Exception as e:
                print(f"Errore invio notifica predizioni: {e}")
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/notifications/settings', methods=['GET'])
        @login_required  
        def get_notification_settings():
            """Restituisce le impostazioni delle notifiche"""
            try:
                email_config = self.settings.get('email', {})
                
                return jsonify({
                    'success': True,
                    'email_enabled': email_config.get('enabled', False),
                    'recipients_count': len(email_config.get('recipients', [])),
                    'threshold': self.settings.get('threshold', 4.0),
                    'last_update': self.settings.get('last_update')
                })
                
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/admin/email-history', methods=['GET'])
        @login_required
        def get_email_history():
            """Mostra storico invii email (solo admin)"""
            if current_user.username != 'admin':
                return jsonify({'error': 'Accesso negato'}), 403
            
            try:
                # Questa è una versione semplificata - in produzione useresti un database
                # per tracciare lo storico degli invii email
                
                return jsonify({
                    'success': True,
                    'history': [
                        {
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'type': 'prediction_alert',
                            'recipients': len(self.settings['email'].get('recipients', [])),
                            'status': 'example_data'
                        }
                    ],
                    'message': 'Funzionalità storico email da implementare con database persistente'
                })
                
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
            
    def run(self, host='0.0.0.0', port=8080, debug=True):
        """Avvia il server Flask"""
        print(f"Avvio server Flask su {host}:{port}")
        print(f"Soglia allerta attuale: {self.settings['threshold']}%")
        print(f"Email notifiche: {'abilitato' if self.settings['email']['enabled'] else 'disabilitato'}")
        self.app.run(host=host, port=port, debug=debug, use_reloader=False)

if __name__ == '__main__':
    server = MiningServer()
    server.run()