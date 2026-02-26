# Webserver_con_YAML
Un mini-server web creato in Python. Visualizza pagine HTML nel browser. Configurabile con un file esterno (YAML). Implementata anche la gestione di più persone contemporaneamente.

## Scelte Implementative

### 1. Architettura Multi-threaded
Per evitare che il server si blocchi durante la gestione di una richiesta, è stato utilizzato il modulo `threading`.
* **Logica:** Ogni volta che un client si connette, il server principale accetta la connessione e delega il lavoro a un nuovo "thread" dedicato.

### 2. Configurazione Esterna via YAML
Invece di scrivere i parametri (IP, porta, rotte) nel codice, abbiamo utilizzato un file `server_config.yaml`.
* **Flessibilità:** È possibile cambiare la porta o aggiungere nuove pagine web semplicemente modificando un file di testo, senza toccare il codice Python.
* **Sicurezza (Default):** Il sistema include una funzione di validazione che garantisce valori di default sicuri nel caso il file YAML sia incompleto o errato.

### 3. Gestione dei Contenuti (MIME Types)
Il server non invia solo testo, ma "spiega" al browser cosa sta ricevendo.
* **Implementazione:** Attraverso un dizionario di mappatura, il server associa le estensioni dei file al loro `MIME Type` corretto.
* **Risultato:** Il browser renderizza correttamente le pagine HTML complete di stili e immagini.

### 4. Hot Reload (Ricaricamento a Runtime)
Una delle caratteristiche più avanzate è la rotta speciale `/reload-config`.
* **Meccanismo:** Se il server riceve una richiesta GET su questo URL, richiama la funzione di caricamento della configurazione aggiornando la variabile globale `CONFIG`.
* **Utilità:** Permette di modificare le rotte o le impostazioni del server "al volo" senza dover riavviare il processo.
