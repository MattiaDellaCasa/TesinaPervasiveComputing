Tesina Pervasive Computing & Servizi Cloud 

Studenti: Della Casa Mattia, Fiorini Fabio, Gazzini Andrea e Marzella Eugenio.

Struttura del progetto:

File necesari per l'avviamento:
Requirements.txt e Requirements_server.txt sono due file nei quali sono presenti tutte le librerie necessarie per i vari programmi python realizzati.
Dockerfile.client e Dockerfile.server sono due file contenitori nei quali sono riportate le dipendenze del sistema necesssarie per avviare il progetto.
Questi due documenti sono poi richiamati dal Docker-compose.yml che altro non è che un contenitore di più grandi dimensioni che comprende entrambre i Docker oltre che altre dipendenze per il progetto.
Infine, il file start_mining_server.sh è un file che permette in automatico di leggere tutti i file dalla cartella del progetto (tra cui docker-compose) e permette di avviare il tutto.

File di input:
Il file di input va inserito nella cartella data ed è un file.csv di enormi dimensioni che per praticità è stato ridotto.

File interni self-generated:
Nella cartella è possibile trovare una cartella chiamata __pycache__ che contiene al suo interno file di cache in grado di risparmiare tempo computazionale nello svolgimento di funzioni python se quella
funzione è stata precedentemente svolta (e quindi salvata nei cache).
Inoltre, sono anche presenti nella cartella 'Log' i file di log del server e del client nei quali è possibile visionare le notifiche e le interazioni che sono avvenute durante l'esecuzione del programma.
Infine, nella cartella 'mosquitto' sono presenti alcuni file necessari per il collegamento client server.

File JSON:
Nel progetto sono presenti due file JSON denominati credentials.json e settings.json (inserito nella cartella config). Il primo è un file all'interno del quale sono presenti le credenziali per accedere a 
google cloud (Firestore) e per dare all'account service i diritti di scrittura ed elaborazione dei dati. Il secondo, invece, contiene al suo interno la memoria delle email che possono essere aggiiunte sulla pagina web.

Cartella Templates:
All'interno di questa cartella possiamo trovare tutti i documenti HTML necessari per visualizzare la pagina web.

File Python:

mqtt_client.py: è il file che legge il file di dati .csv e invia questi dati al server con il protocollo MQTT. in particolare, è in questo file che avviene il collegamento con Firestore grazie alle credenziali presenti in credentials.json.

ml_predictor.py: è il file python che crea la predizione con due modelli selezionati.

grafici_mining.py: è il file che genera i grafici presenti sulla pagina web.

email_notification.py: permette la realizzazione e l'invio di email di allerta a determinate condizioni.

main.py: è il file principale che aggrega tutti i file precedentemente realizzati. Il file main.py e mqtt_client.py possono essere avviati da due terminali diversi e permettono il funzionamento del progetto.
