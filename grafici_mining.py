import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import numpy as np

# Variabile globale soglia
CURRENT_THRESHOLD = 4.0

#Aggiorna la soglia per gli allert
def set_alert_threshold(new_threshold):
    global CURRENT_THRESHOLD
    CURRENT_THRESHOLD = float(new_threshold)
    print(f"Soglia allerta aggiornata a: {CURRENT_THRESHOLD}%")

#Mostra la soglia scelta
def get_alert_threshold():
    return CURRENT_THRESHOLD

#recupera dati da firestore per graficarli
def get_data_from_firestore(db, collection_name='mining_data', limit=10000):
    if db is None:
        print("Errore: Database Firestore non configurato")
        return None
    
    try:
        # recupera i documenti ordinati per timestamp in ordine crescente
        docs = db.collection(collection_name).order_by('row_index').limit(limit).get()
        
        data = []
        for doc in docs:
            doc_data = doc.to_dict()
            sensor_data = doc_data.get('sensor_data', {})
            
            sensor_data['timestamp'] = doc_data.get('timestamp')
            sensor_data['row_index'] = doc_data.get('row_index', 0)
            sensor_data['doc_id'] = doc.id
            data.append(sensor_data)
        
        if not data:
            print("Nessun dato disponibile nel database cloud")
            return None
        
        #crea dataframe con dati ordinati
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('row_index')  # Ordina per ordine di invio, non per timestamp
        
        print(f"Caricati {len(df)} campioni da Firestore in ordine cronologico di invio")
        print(f"Range row_index: da {df['row_index'].min()} a {df['row_index'].max()}")
        
        return df
    
    except Exception as e:
        print(f"Errore recupero dati da Firestore: {e}")
        return None

#grafico dashboard
def create_realtime_charts(db=None):
    df = get_data_from_firestore(db, limit=10000)
    
    if df is None or len(df) == 0:
        return {
            'error': 'Nessun dato disponibile nel database cloud. Verificare che il client MQTT stia inviando dati e che Firestore sia configurato correttamente.',
            'stats': {
                'current_silica': 0, 
                'current_ph': 0, 
                'data_points': 0,
                'status': 'NO_DATA'
            }
        }
    
    #usa la soglia preimpostata
    threshold = get_alert_threshold()
    
    #grafico 1: Andamento % Silica Concentrate in ordine di invio
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=df['row_index'],  
        y=df['% Silica Concentrate'],
        mode='lines+markers',
        name='% Silica Concentrate',
        line=dict(color='red', width=2),
        marker=dict(size=4),
        hovertemplate='Riga: %{x}<br>Silica: %{y:.2f}%<extra></extra>'
    ))
    
    fig1.add_hline(y=threshold, line_dash="dash", line_color="orange", 
                   annotation_text=f"Soglia Allerta ({threshold}%)")
    
    fig1.update_layout(
        title='% Silica Concentrate - Dati da Cloud (Ordine di Invio)',
        xaxis_title='Numero Riga Dataset',
        yaxis_title='% Silica',
        hovermode='x unified',
        height=400
    )
    
    #grafico 2: Parametri principali del processo
    fig2 = make_subplots(
        rows=2, cols=2,
        subplot_titles=['% Iron Feed', 'Ore Pulp pH', 'Starch Flow', 'Amina Flow']
    )
    
    fig2.add_trace(go.Scatter(x=df['row_index'], y=df['% Iron Feed'], 
                             mode='lines', name='% Iron Feed', line=dict(color='blue')), 
                             row=1, col=1)
    fig2.add_trace(go.Scatter(x=df['row_index'], y=df['Ore Pulp pH'], 
                             mode='lines', name='pH', line=dict(color='green')), 
                             row=1, col=2)
    fig2.add_trace(go.Scatter(x=df['row_index'], y=df['Starch Flow'], 
                             mode='lines', name='Starch Flow', line=dict(color='purple')), 
                             row=2, col=1)
    fig2.add_trace(go.Scatter(x=df['row_index'], y=df['Amina Flow'], 
                             mode='lines', name='Amina Flow', line=dict(color='orange')), 
                             row=2, col=2)
    
    fig2.update_layout(
        title='Parametri di Processo - Dati da Cloud',
        height=600,
        showlegend=False
    )
    
    #etichette asse x per tutti i subplot
    fig2.update_xaxes(title_text="Numero Riga Dataset", row=1, col=1)
    fig2.update_xaxes(title_text="Numero Riga Dataset", row=1, col=2)
    fig2.update_xaxes(title_text="Numero Riga Dataset", row=2, col=1)
    fig2.update_xaxes(title_text="Numero Riga Dataset", row=2, col=2)
    
    #grafico 3: Distribuzione % Silica
    recent_data = df.tail(100)  #ultimi 100 punti ricevuti
    
    if '% Silica Concentrate' in df.columns:
        fig3 = go.Figure(data=[go.Histogram(
            x=recent_data['% Silica Concentrate'],
            nbinsx=20,
            name='Distribuzione % Silica',
            marker_color='lightblue'
        )])
        
        fig3.add_vline(x=threshold, line_dash="dash", line_color="orange", 
                      annotation_text=f"Soglia ({threshold}%)")
        
        fig3.update_layout(
            title=f'Distribuzione % Silica (Ultimi {len(recent_data)} campioni ricevuti)',
            xaxis_title='% Silica Concentrate',
            yaxis_title='Frequenza',
            height=400
        )
    else:
        fig3 = go.Figure()
        fig3.update_layout(
            title='Distribuzione % Silica - Colonna non trovata',
            xaxis_title='% Silica Concentrate',
            yaxis_title='Frequenza',
            height=400
        )
    
    df_sorted = df.sort_values('row_index')  #ordina per row_index
    latest_data = df_sorted.iloc[-1] if len(df_sorted) > 0 else {}
    
    print(f"DEBUG: latest_data = {latest_data}")
    print(f"DEBUG: % Silica Concentrate = {latest_data.get('% Silica Concentrate', 'NON TROVATO')}")
    
    #conta quanti valori correnti superano la soglia
    current_alerts = int((df['% Silica Concentrate'] > threshold).sum())
    
    stats = {
        'current_silica': float(latest_data.get('% Silica Concentrate', 0)),
        'avg_silica': float(df['% Silica Concentrate'].mean()),
        'std_silica': float(df['% Silica Concentrate'].std()),
        'max_silica': float(df['% Silica Concentrate'].max()),
        'min_silica': float(df['% Silica Concentrate'].min()),
        'current_ph': float(latest_data.get('Ore Pulp pH', 0)),
        'current_iron': float(latest_data.get('% Iron Feed', 0)),
        'data_points': len(df),
        'last_row_index': int(latest_data.get('row_index', 0)),
        'current_alerts': current_alerts,
        'alert_threshold': threshold,
        'status': 'CLOUD_DATA_OK'
    }
    
    print(f"DEBUG: stats = {stats}")
    
    return {
        'silica_trend': json.loads(fig1.to_json()),
        'silica_trend_simple': {
            'data': [{
                'x': df['row_index'].tolist(),
                'y': df['% Silica Concentrate'].tolist(),
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': '% Silica Concentrate',
                'line': {'color': 'red', 'width': 2}
            }],
            'layout': {
                'title': '% Silica Concentrate - Dati da Cloud',
                'xaxis': {'title': 'Numero Riga Dataset'},
                'yaxis': {'title': '% Silica'},
                'height': 400,
                'shapes': [{
                    'type': 'line',
                    'x0': 0, 'x1': 1, 'xref': 'paper',
                    'y0': threshold, 'y1': threshold,
                    'line': {'color': 'orange', 'width': 2, 'dash': 'dash'}
                }],
                'annotations': [{
                    'x': 0.02, 'y': threshold,
                    'xref': 'paper', 'yref': 'y',
                    'text': f'Soglia Allerta ({threshold}%)',
                    'showarrow': False,
                    'bgcolor': 'orange',
                    'bordercolor': 'orange',
                    'font': {'color': 'white'}
                }]
            }
        },
        'process_params': json.loads(fig2.to_json()),
        'silica_distribution': json.loads(fig3.to_json()),
        'stats': stats  # QUESTA È LA CORREZIONE PRINCIPALE
    }

#grafici storico parametri
def create_historical_charts(db=None):
    df = get_data_from_firestore(db, limit=10000)
    
    if df is None or len(df) == 0:
        return {
            'error': 'Nessun dato storico disponibile nel database cloud',
            'message': 'Assicurarsi che il client MQTT abbia inviato dati sufficienti'
        }
    
    threshold = get_alert_threshold()
    
    correlation_params = ['% Iron Feed', '% Silica Feed', 'Ore Pulp pH', 
                         'Starch Flow', '% Silica Concentrate']
    
    #verifica che le colonne esistano
    available_params = [col for col in correlation_params if col in df.columns]
    
    if len(available_params) < 2:
        return {'error': 'Dati insufficienti per analisi correlazione'}
    
    corr_data = df[available_params].corr()
    
    fig1 = go.Figure(data=go.Heatmap(
        z=corr_data.values,
        x=corr_data.columns,
        y=corr_data.columns,
        colorscale='RdYlBu',
        zmid=0,
        text=np.round(corr_data.values, 2),
        texttemplate='%{text}',
        textfont={"size": 10}
    ))
    
    fig1.update_layout(
        title='Matrice di Correlazione - Dati da Cloud',
        height=500
    )
    
    #divisi i dati in gruppi di 100 righe per vedere l'evoluzione
    df['batch'] = df['row_index'] // 100
    batch_stats = df.groupby('batch')['% Silica Concentrate'].agg(['mean', 'std', 'count']).reset_index()
    batch_stats['batch_label'] = batch_stats['batch'].apply(lambda x: f"Righe {x*100}-{(x+1)*100}")
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=batch_stats['batch_label'],
        y=batch_stats['mean'],
        mode='lines+markers',
        name='Media per batch',
        error_y=dict(type='data', array=batch_stats['std'], visible=True),
        line=dict(color='blue', width=3)
    ))
    
    fig2.add_hline(y=threshold, line_dash="dash", line_color="orange", 
                   annotation_text=f"Soglia Allerta ({threshold}%)")
    
    fig2.update_layout(
        title='Andamento % Silica per Batch di Dati (Dati da Cloud)',
        xaxis_title='Batch di Righe',
        yaxis_title='% Silica Concentrate (Media)',
        height=400,
        xaxis_tickangle=-45
    )
    
    try:
        df['silica_range'] = pd.cut(df['% Silica Concentrate'], 
                                   bins=5, 
                                   labels=['Molto Basso', 'Basso', 'Medio', 'Alto', 'Molto Alto'])
        
        fig3 = go.Figure()
        for silica_range in df['silica_range'].unique():
            if pd.notna(silica_range):
                data = df[df['silica_range'] == silica_range]['% Iron Feed']
                fig3.add_trace(go.Box(y=data, name=str(silica_range)))
        
        fig3.update_layout(
            title='% Iron Feed vs Range % Silica (Dati da Cloud)',
            xaxis_title='Range % Silica',
            yaxis_title='% Iron Feed',
            height=400
        )
        
        range_analysis = json.loads(fig3.to_json())
    except Exception as e:
        print(f"Errore analisi range: {e}")
        range_analysis = {'error': 'Impossibile creare analisi range'}
    
    #Allerte storiche
    historical_alerts = int((df['% Silica Concentrate'] > threshold).sum())
    
    return {
        'correlation_matrix': json.loads(fig1.to_json()),
        'batch_trend': json.loads(fig2.to_json()),
        'range_analysis': range_analysis,
        'summary': {
            'total_samples': len(df),
            'row_range': {
                'start': int(df['row_index'].min()),
                'end': int(df['row_index'].max())
            },
            'avg_silica': float(df['% Silica Concentrate'].mean()),
            'historical_alerts': historical_alerts,
            'alert_threshold': threshold,
            'data_source': 'CLOUD_ONLY'
        }
    }

#grafici predizioni
def create_prediction_charts(db=None, predictor=None, hours_ahead=1):
    print(f"DEBUG PREDICTION: Avvio creazione grafici predizioni per {hours_ahead} ore")
    
    df = get_data_from_firestore(db, limit=10000)
    
    if df is None or len(df) == 0:
        print("DEBUG PREDICTION: Nessun dato disponibile")
        return {
            'error': 'Impossibile caricare i dati dal cloud per le predizioni',
            'message': 'Verificare che ci siano dati nel database Firestore',
            'prediction_chart': {
                'data': [],
                'layout': {'title': 'Nessun dato disponibile per predizioni'}
            },
            'prediction_stats': {
                'avg_prediction': 0,
                'max_prediction': 0,
                'min_prediction': 0,
                'alerts_predicted': 0,
                'avg_confidence': 0,
                'prediction_horizon': 'Nessun dato',
                'based_on_cloud_data': False,
                'last_real_value': 0,
                'last_row_index': 0,
                'alert_threshold': get_alert_threshold(),
                'data_source': 'NO_DATA'
            }
        }
    
    print(f"DEBUG PREDICTION: Caricati {len(df)} campioni dal cloud")
    
    required_columns = ['% Silica Concentrate', 'row_index']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"DEBUG PREDICTION: Colonne mancanti: {missing_columns}")
        return {
            'error': f'Colonne mancanti nei dati: {missing_columns}',
            'prediction_chart': {'data': [], 'layout': {'title': 'Dati incompleti'}},
            'prediction_stats': {
                'avg_prediction': 0, 'max_prediction': 0, 'min_prediction': 0,
                'alerts_predicted': 0, 'avg_confidence': 0,
                'prediction_horizon': 'Errore dati', 'based_on_cloud_data': False,
                'last_real_value': 0, 'last_row_index': 0,
                'alert_threshold': get_alert_threshold(), 'data_source': 'ERROR'
            }
        }
    
    last_data = df.iloc[-1].to_dict() if len(df) > 0 else {}
    last_row_index = int(last_data.get('row_index', 0))
    threshold = get_alert_threshold()
    
    print(f"DEBUG PREDICTION: Ultimo row_index: {last_row_index}, Soglia: {threshold}")
    
    #indici futuri da prevedere
    num_predictions = max(3, hours_ahead * 3) 
    future_indices = list(range(last_row_index + 1, last_row_index + 1 + num_predictions))
    
    print(f"DEBUG PREDICTION: Genero {len(future_indices)} predizioni future")
    
    predictions = []
    for i, future_index in enumerate(future_indices):
        #usa gli ultimi dati reali come base per la predizione
        simulated_data = last_data.copy()
        
        variation_params = ['% Iron Feed', '% Silica Feed', 'Ore Pulp pH', 'Starch Flow']
        for param in variation_params:
            if param in simulated_data and pd.notna(simulated_data[param]):
                base_value = simulated_data[param]
                # Variazione del 2% con tendenza verso la media storica
                if param in df.columns:
                    historical_mean = df[param].mean()
                    trend_factor = (historical_mean - base_value) * 0.1
                    variation = np.random.normal(trend_factor, abs(base_value) * 0.02)
                    simulated_data[param] = base_value + variation
        
        #predizione
        pred = None
        if predictor and hasattr(predictor, 'predict_silica'):
            try:
                pred = predictor.predict_silica(simulated_data)
                print(f"DEBUG PREDICTION: Predizione ML per indice {future_index}: {pred}")
            except Exception as e:
                print(f"DEBUG PREDICTION: Errore predizione ML: {e}")
                pred = None
        
        #modello semplificato
        if pred is None:
            base_silica = last_data.get('% Silica Concentrate', df['% Silica Concentrate'].mean())
            ph_effect = (simulated_data.get('Ore Pulp pH', 10) - 10) * 0.1
            iron_effect = (simulated_data.get('% Iron Feed', 60) - 60) * 0.02
            pred = base_silica + ph_effect + iron_effect + np.random.normal(0, 0.2)
            print(f"DEBUG PREDICTION: Predizione fallback per indice {future_index}: {pred}")
        
        predictions.append({
            'future_index': future_index,
            'predicted_silica': max(0.1, pred),
            'confidence': max(0.3, 1.0 - (i * 0.1))
        })
    
    pred_df = pd.DataFrame(predictions)
    print(f"DEBUG PREDICTION: Creato DataFrame predizioni con {len(pred_df)} righe")
    
    #conta quante predizioni superano la soglia
    alerts_predicted = int((pred_df['predicted_silica'] > threshold).sum())
    print(f"DEBUG PREDICTION: Allerte previste: {alerts_predicted}/{len(pred_df)} (soglia: {threshold}%)")
    
    #grafico predizioni
    fig1 = go.Figure()
    
    recent_df = df.tail(50)
    print(f"DEBUG PREDICTION: Aggiungo {len(recent_df)} dati storici al grafico")
    
    fig1.add_trace(go.Scatter(
        x=recent_df['row_index'].tolist(),
        y=recent_df['% Silica Concentrate'].tolist(),
        mode='lines+markers',
        name='Dati Reali (Cloud)',
        line=dict(color='blue', width=2),
        marker=dict(size=6)
    ))
    
    #predizioni future
    print(f"DEBUG PREDICTION: Aggiungo {len(pred_df)} predizioni al grafico")
    fig1.add_trace(go.Scatter(
        x=pred_df['future_index'].tolist(),
        y=pred_df['predicted_silica'].tolist(),
        mode='lines+markers',
        name=f'Predizioni (prossimo minuto)' if hours_ahead == 1 else f'Predizioni (prossimi {hours_ahead} minuti)',
        line=dict(color='red', dash='dash', width=2),
        marker=dict(size=6)
    ))
    
    #banda di confidenza
    upper_bound = pred_df['predicted_silica'] + (1 - pred_df['confidence'])
    lower_bound = pred_df['predicted_silica'] - (1 - pred_df['confidence'])
    
    fig1.add_trace(go.Scatter(
        x=pred_df['future_index'].tolist(),
        y=upper_bound.tolist(),
        fill=None,
        mode='lines',
        line_color='rgba(0,0,0,0)',
        showlegend=False
    ))
    
    fig1.add_trace(go.Scatter(
        x=pred_df['future_index'].tolist(),
        y=lower_bound.tolist(),
        fill='tonexty',
        mode='lines',
        line_color='rgba(0,0,0,0)',
        name='Banda Confidenza',
        fillcolor='rgba(255,0,0,0.2)'
    ))
    
    #soglia dinamica corrente
    fig1.add_hline(y=threshold, line_dash="dash", line_color="orange", 
                   annotation_text=f"Soglia Allerta ({threshold}%)")
    
    fig1.update_layout(
        title=f'Predizioni % Silica - Prossimo Minuto' if hours_ahead == 1 else f'Predizioni % Silica - Prossimi {hours_ahead} Minuti',
        xaxis_title='Numero Riga Dataset',
        yaxis_title='% Silica',
        height=500,
        hovermode='x unified',
        showlegend=True
    )
    
    #statistiche predizioni
    pred_stats = {
        'avg_prediction': float(pred_df['predicted_silica'].mean()),
        'max_prediction': float(pred_df['predicted_silica'].max()),
        'min_prediction': float(pred_df['predicted_silica'].min()),
        'alerts_predicted': alerts_predicted,  # Ora conta correttamente con soglia dinamica
        'avg_confidence': float(pred_df['confidence'].mean() * 100),
        'prediction_horizon': f"{len(pred_df)} righe future",
        'based_on_cloud_data': True,
        'last_real_value': float(last_data.get('% Silica Concentrate', 0)),
        'last_row_index': last_row_index,
        'alert_threshold': threshold,  # Includi soglia corrente
        'data_source': 'CLOUD_ONLY'
    }
    
    print(f"DEBUG PREDICTION: Statistiche predizioni: {pred_stats}")
    
    try:
        chart_json = json.loads(fig1.to_json())
        print("DEBUG PREDICTION: Conversione JSON del grafico completata")
    except Exception as e:
        print(f"DEBUG PREDICTION: Errore conversione JSON: {e}")
        chart_json = {'data': [], 'layout': {'title': 'Errore conversione grafico'}}
    
    result = {
        'prediction_chart': chart_json,
        'prediction_stats': pred_stats
    }
    
    print("DEBUG PREDICTION: Ritorno risultati completi")
    return result

def get_raw_data_for_charts(db=None):
    """Restituisce dati grezzi per i grafici dei parametri"""
    df = get_data_from_firestore(db, limit=10000)
    
    if df is None or len(df) == 0:
        return {
            'error': 'Nessun dato disponibile nel database cloud',
            'available_columns': []
        }
    
    print(f"DEBUG RAW DATA: Colonne disponibili: {df.columns.tolist()}")
    print(f"DEBUG RAW DATA: Forma DataFrame: {df.shape}")
    
    threshold = get_alert_threshold()
    
    result = {
        'error': None,
        'data_points': len(df),
        'available_columns': df.columns.tolist(),
        'x_data': df['row_index'].tolist(),
        'alert_threshold': threshold,
        'parameters': {}
    }
    
    target_parameters = [
        '% Iron Feed',
        'Ore Pulp pH', 
        'Starch Flow',
        'Amina Flow',
        '% Silica Concentrate'  
    ]
    

    for param in target_parameters:
        if param in df.columns:
            result['parameters'][param] = {
                'values': df[param].tolist(),
                'available': True,
                'min': float(df[param].min()),
                'max': float(df[param].max()),
                'mean': float(df[param].mean())
            }
            print(f"DEBUG RAW DATA: {param} - {len(df[param])} valori, range: {df[param].min():.2f} - {df[param].max():.2f}")
        else:
            result['parameters'][param] = {
                'values': [],
                'available': False,
                'min': 0,
                'max': 0,
                'mean': 0
            }
            print(f"DEBUG RAW DATA: {param} - COLONNA NON TROVATA")
    
    return result