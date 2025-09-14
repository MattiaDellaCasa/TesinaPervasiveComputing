import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
import os

class EmailNotifier:
    def __init__(self, smtp_server="smtp.gmail.com", smtp_port=465):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        
        self.sender_email ='fabiofiorini96@gmail.com'
        self.sender_password = 'necf kbqs ixjy trgh'
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Contatori per statistiche
        self.sent_count = 0
        self.failed_count = 0
    
    def send_email(self, recipient_email, subject, message, is_html=False):
        """Invia una email"""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = recipient_email
            
            if is_html:
                part = MIMEText(message, "html")
            else:
                part = MIMEText(message, "plain")
            
            msg.attach(part)
            
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            self.sent_count += 1
            self.logger.info(f"Email inviata con successo a {recipient_email}")
            return True
            
        except Exception as e:
            self.failed_count += 1
            self.logger.error(f"Errore invio email a {recipient_email}: {e}")
            return False
    
    def send_alert_email(self, recipients, prediction_value, threshold, sensor_data):
        """Invia email di allerta per valori di Silica sopra soglia"""
        subject = f"🚨 ALLERTA MINING: Silica {prediction_value:.2f}% > {threshold}%"
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .alert {{ background-color: #f8d7da; border: 1px solid #f5c6cb; 
                          padding: 20px; border-radius: 5px; }}
                .header {{ color: #721c24; font-size: 24px; font-weight: bold; }}
                .critical {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="alert">
                <div class="header">⚠️ ALLERTA PROCESSO MINERARIO</div>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p class="critical">Predizione % Silica Concentrate: {prediction_value:.3f}%</p>
                <p>Soglia configurata: {threshold}%</p>
                <p><strong>Azione richiesta:</strong> Verificare immediatamente il processo di flotazione</p>
                
                <h3>Dati Sensori Attuali:</h3>
                <ul>
                    <li>% Iron Feed: {sensor_data.get('% Iron Feed', 'N/A')}</li>
                    <li>% Silica Feed: {sensor_data.get('% Silica Feed', 'N/A')}</li>
                    <li>Ore Pulp pH: {sensor_data.get('Ore Pulp pH', 'N/A')}</li>
                    <li>Starch Flow: {sensor_data.get('Starch Flow', 'N/A')}</li>
                </ul>
                
                <p><strong>Sistema di Monitoraggio Mining</strong></p>
            </div>
        </body>
        </html>
        """
        
        text_message = f"""
        ALLERTA PROCESSO MINERARIO
        ========================
        
        Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Predizione % Silica Concentrate: {prediction_value:.3f}%
        Soglia configurata: {threshold}%
        
        AZIONE RICHIESTA: Verificare immediatamente il processo!
        
        Dati Sensori:
        - % Iron Feed: {sensor_data.get('% Iron Feed', 'N/A')}
        - % Silica Feed: {sensor_data.get('% Silica Feed', 'N/A')}
        - Ore Pulp pH: {sensor_data.get('Ore Pulp pH', 'N/A')}
        - Starch Flow: {sensor_data.get('Starch Flow', 'N/A')}
        """
        
        success_count = 0
        if isinstance(recipients, str):
            recipients = [recipients]
        
        for recipient in recipients:
            if self.send_email(recipient, subject, html_message, is_html=True):
                success_count += 1
            elif self.send_email(recipient, subject, text_message, is_html=False):
                success_count += 1
        
        self.logger.info(f"Email di allerta inviate: {success_count}/{len(recipients)}")
        return success_count
    
    def send_prediction_alert(self, recipients, prediction_period, alerts_count, threshold, 
                             max_prediction=None, avg_prediction=None, prediction_horizon=None):
        """Invia email di allerta per predizioni future"""
        subject = f"🔮 ALLERTA PREDIZIONI: {alerts_count} allerte nel {prediction_period}"
        
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
                <div class="header">🔮 ALLERTA PREDIZIONI MINING</div>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p class="critical">Nel {prediction_period} sono previste <strong>{alerts_count} allerte</strong> 
                   per percentuale silica superiore alla soglia di <strong>{threshold}%</strong></p>
                
                <div class="stats">
                    <h4>Dettagli Predizioni:</h4>
                    <ul>
        """
        
        if max_prediction is not None:
            html_message += f"<li><strong>Massimo predetto:</strong> {max_prediction:.2f}% Silica</li>"
        if avg_prediction is not None:
            html_message += f"<li><strong>Media predetta:</strong> {avg_prediction:.2f}% Silica</li>"
        if prediction_horizon is not None:
            html_message += f"<li><strong>Orizzonte temporale:</strong> {prediction_horizon}</li>"
            
        html_message += f"""
                        <li><strong>Soglia configurata:</strong> {threshold}%</li>
                        <li><strong>Allerte previste:</strong> {alerts_count}</li>
                    </ul>
                </div>
                
                <p><strong>🎯 Azione raccomandata:</strong> Monitorare attentamente il processo nelle prossime ore 
                   e verificare i parametri di flotazione se necessario.</p>
                
                <div class="footer">
                    <p>Notifica generata automaticamente dal Sistema di Monitoraggio Mining<br>
                    Sistema: <strong>Predizioni ML</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Versione testo
        text_message = f"""
        ALLERTA PREDIZIONI MINING
        ========================
        
        Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Nel {prediction_period} sono previste {alerts_count} allerte
        per percentuale silica superiore alla soglia di {threshold}%
        
        DETTAGLI PREDIZIONI:
        """
        
        if max_prediction is not None:
            text_message += f"- Massimo predetto: {max_prediction:.2f}% Silica\n        "
        if avg_prediction is not None:
            text_message += f"- Media predetta: {avg_prediction:.2f}% Silica\n        "
        if prediction_horizon is not None:
            text_message += f"- Orizzonte temporale: {prediction_horizon}\n        "
            
        text_message += f"""
        - Soglia configurata: {threshold}%
        - Allerte previste: {alerts_count}
        
        AZIONE RACCOMANDATA: 
        Monitorare attentamente il processo nelle prossime ore
        e verificare i parametri di flotazione se necessario.
        
        Sistema di Monitoraggio Mining - Predizioni ML
        """
        
        success_count = 0
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(',') if r.strip()]
        
        for recipient in recipients:
            if recipient:
                if self.send_email(recipient, subject, html_message, is_html=True):
                    success_count += 1
                elif self.send_email(recipient, subject, text_message, is_html=False):
                    success_count += 1
        
        self.logger.info(f"Email predizioni inviate: {success_count}/{len(recipients)}")
        return success_count
    
    def send_test_email(self, recipients, user_name="Sistema"):
        """Invia email di test"""
        subject = "Test Email - Sistema Mining"
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .test {{ background-color: #d1ecf1; border: 1px solid #bee5eb; 
                         padding: 20px; border-radius: 5px; border-left: 4px solid #17a2b8; }}
                .header {{ color: #0c5460; font-size: 20px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="test">
                <div class="header">✅ EMAIL DI TEST - SISTEMA MINING</div>
                <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Utente richiedente:</strong> {user_name}</p>
                <p>Questo è un messaggio di test per verificare che le notifiche email funzionino correttamente.</p>
                <p>Se ricevi questo messaggio, la configurazione email è <strong>corretta</strong> ✅</p>
                
                <h4>Informazioni Sistema:</h4>
                <ul>
                    <li>Server SMTP: {self.smtp_server}:{self.smtp_port}</li>
                    <li>Email mittente: {self.sender_email}</li>
                    <li>Email inviate con successo: {self.sent_count}</li>
                    <li>Email fallite: {self.failed_count}</li>
                </ul>
                
                <hr>
                <small>Sistema di Monitoraggio Mining - Test Automatico</small>
            </div>
        </body>
        </html>
        """
        
        text_message = f"""
        EMAIL DI TEST - SISTEMA MINING
        =============================
        
        Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        Utente richiedente: {user_name}
        
        Questo è un messaggio di test per verificare che le notifiche 
        email funzionino correttamente.
        
        Se ricevi questo messaggio, la configurazione email è CORRETTA.
        
        Informazioni Sistema:
        - Server SMTP: {self.smtp_server}:{self.smtp_port}
        - Email mittente: {self.sender_email}
        - Email inviate con successo: {self.sent_count}
        - Email fallite: {self.failed_count}
        
        Sistema di Monitoraggio Mining - Test Automatico
        """
        
        success_count = 0
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(',') if r.strip()]
        
        for recipient in recipients:
            if recipient:
                if self.send_email(recipient, subject, html_message, is_html=True):
                    success_count += 1
                elif self.send_email(recipient, subject, text_message, is_html=False):
                    success_count += 1
        
        self.logger.info(f"Email di test inviate: {success_count}/{len(recipients)}")
        return success_count
    
    def get_statistics(self):
        """Restituisce statistiche invii email"""
        return {
            'sent_count': self.sent_count,
            'failed_count': self.failed_count,
            'success_rate': (self.sent_count / (self.sent_count + self.failed_count) * 100) if (self.sent_count + self.failed_count) > 0 else 0
        }