import socket
import threading
import yaml
import logging
import os

# Dizionario globale che conterrà la configurazione letta dal file YAML
CONFIG = {}


def valida_struttura_config(data):
    if 'server' in data:
        if not isinstance(data['server'], dict):
            raise ValueError("La sezione 'server' deve essere un dizionario.")

        if 'port' in data['server'] and not isinstance(data['server']['port'], int):
            raise ValueError("La porta deve essere un numero intero.")

        if 'host' in data['server'] and not isinstance(data['server']['host'], str):
            raise ValueError("L'host deve essere una stringa.")

    if 'routes' in data and not isinstance(data['routes'], list):
        raise ValueError("La sezione 'routes' deve essere una lista.")

def valida_e_imposta_default(data):
    if not data:
        data = {}

    # Configurazione di rete se non specificate
    data.setdefault('server', {})
    data['server'].setdefault('host', '0.0.0.0')
    data['server'].setdefault('port', 8080)
    data['server'].setdefault('max_connections', 5)

    # Percorsi: imposta la cartella 'public' come radice dei file statici e definisce la rotta home
    data.setdefault('static_dir', './public')
    data.setdefault('routes', [{'path': '/', 'file': 'index.html'}])

    # Logging: definisce il nome del file di registro e il livello
    data.setdefault('logging', {'file': 'server.log', 'level': 'INFO'})

    # Mappa delle estensioni file ai tipi MIME
    data.setdefault('mime_types', {
        '.html': 'text/html',
        '.css': 'text/css',
        '.png': 'image/png'
    })

    # Associa i codici di errore HTTP ai rispettivi file HTML
    data.setdefault('error_pages', {404: '404.html', 500: '500.html'})

    return data


def carica_configurazione():
    try:
        with open("server_config.yaml", "r") as f:
            data = yaml.safe_load(f)
            valida_struttura_config(data)
            return valida_e_imposta_default(data)

    except FileNotFoundError:
        # Il file di configurazione non esiste: si prosegue con i default
        print("ERRORE: file server_config.yaml non trovato. Uso configurazione di default.")
        return valida_e_imposta_default({})

    except yaml.YAMLError as e:
        # Il file esiste ma contiene sintassi YAML non valida
        print(f"ERRORE: file YAML malformato: {e}. Uso configurazione di default.")
        return valida_e_imposta_default({})

    except Exception as e:
        # Qualsiasi altro errore imprevisto durante il caricamento
        print(f"Errore imprevisto nel caricamento configurazione: {e}")
        return valida_e_imposta_default({})


def invia_risposta_errore(codice, messaggio_log):
    # Mappa i codici HTTP più comuni alla loro descrizione
    descrizioni = {
        404: "Not Found",
        500: "Internal Server Error",
    }
    testo_stato = descrizioni.get(codice, "Error")

    logging.error(messaggio_log)

    # Recupera il nome del file HTML di errore dalla config, o usa il default "{codice}.html"
    nome_file_errore = CONFIG['error_pages'].get(codice, f"{codice}.html")
    percorso_errore = os.path.join(CONFIG['static_dir'], nome_file_errore)

    try:
        with open(percorso_errore, "rb") as f:
            corpo = f.read()
    except FileNotFoundError:
        # La pagina di errore personalizzata non esiste: si genera una risposta HTML minimale
        logging.warning(f"Pagina errore non trovata: {percorso_errore}")
        corpo = f"<h1>{codice} {testo_stato}</h1><p>Risorsa non disponibile.</p>".encode()

    # Costruisce l'header HTTP con codice di stato e content-type
    header = f"HTTP/1.1 {codice} {testo_stato}\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
    return header.encode() + corpo


def gestisci_client(socket_client, indirizzo):
    global CONFIG
    try:
        # Riceve la richiesta HTTP del browser
        dati = socket_client.recv(4096).decode('utf-8')
        if not dati: return

        # Estrae la prima riga della richiesta
        riga_richiesta = dati.split("\r\n")[0]
        parti = riga_richiesta.split(" ")
        if len(parti) < 2: return

        # Isola il metodo e l'URL richiesto
        metodo, percorso = parti[0], parti[1]
        logging.info(f"Richiesta: {metodo} {percorso} da {indirizzo}")

        # Permette di ricaricare il file YAML senza spegnere il server
        if metodo == "GET" and percorso == "/reload-config":
            CONFIG = carica_configurazione()
            logging.info("Configurazione ricaricata con successo tramite richiesta web!")
            risposta = b"HTTP/1.1 200 OK\r\n\r\nConfigurazione ricaricata!"
            socket_client.sendall(risposta)
            return

        if metodo == "GET":
            nome_file = None
            # Scorre le rotte definite nel CONFIG per vedere se l'URL richiesto è mappato su un file
            for rotta in CONFIG['routes']:
                if rotta['path'] == percorso:
                    nome_file = rotta['file']
                    break

            if nome_file:
                # Se la rotta esiste, costruisce il percorso del file sul sistema
                percorso_completo = os.path.join(CONFIG['static_dir'], nome_file)
                try:
                    # Identifica l'estensione e assegna il MIME type corretto
                    ext = os.path.splitext(nome_file)[1]
                    tipo_mime = CONFIG['mime_types'].get(ext, 'application/octet-stream')

                    # Legge il contenuto del file
                    with open(percorso_completo, "rb") as f:
                        contenuto = f.read()

                    # Crea l'intestazione di successo 200 OK
                    header = f"HTTP/1.1 200 OK\r\nContent-Type: {tipo_mime}; charset=utf-8\r\n\r\n"
                    risposta = header.encode() + contenuto
                except FileNotFoundError:
                    # Se il file dichiarato nel YAML non esiste fisicamente sul disco
                    risposta = invia_risposta_errore(404, f"File fisico non trovato: {percorso_completo}")
            else:
                # Se l'utente richiede un URL che non è presente nella lista 'routes' del YAML
                risposta = invia_risposta_errore(404, f"Rotta non definita nel YAML: {percorso}")

        else:
            # Rifiuta metodi diversi da GET
            risposta = b"HTTP/1.1 405 Method Not Allowed\r\n\r\nMetodo non supportato."

        # Invia la risposta completa al client
        socket_client.sendall(risposta)

    except Exception as e:
        # Gestisce crash imprevisti durante la gestione della richiesta
        risposta = invia_risposta_errore(500, f"Errore interno: {e}")
        socket_client.sendall(risposta)
    finally:
        # Chiude sempre la connessione per non lasciare socket appese
        socket_client.close()


def avvia_server():
    global CONFIG
    # Inizializza la configurazione all'avvio
    CONFIG = carica_configurazione()
    CONFIG['routes'].append({'path': '/index', 'file': 'index.html'})

    # Configura il logger per scrivere nel file specificato con data e ora
    livello_logging = getattr(logging, CONFIG['logging']['level'].upper(), logging.INFO)

    logging.basicConfig(
        filename=CONFIG['logging']['file'],
        level=livello_logging,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Crea una socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Permette il riavvio immediato sulla stessa porta
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        host, port = CONFIG['server']['host'], CONFIG['server']['port']
        # Lega il socket all'indirizzo e porta scelti
        server.bind((host, port))
        # Mette il server in ascolto, definendo quante connessioni mettere in coda
        server.listen(CONFIG['server']['max_connections'])

        print(f"Server in esecuzione su http://{host}:{port}")
        logging.info(f"Server avviato su {host}:{port}")

        # Ciclo infinito per accettare nuove connessioni
        while True:
            # Si blocca qui finché un client non si connette
            conn, addr = server.accept()
            # Avvia un nuovo thread per gestire la richiesta senza bloccare l'ascolto di altri client
            threading.Thread(target=gestisci_client, args=(conn, addr)).start()
    except Exception as e:
        print(f"Errore critico avvio: {e}")


if __name__ == "__main__":
    avvia_server()
