# 🚀 3CX → Yealink Sync PRO - Quick Start

**Mit integriertem Web-Setup-Interface & direkter 3CX-API**

---

## Was ist neu in der PRO-Version?

✨ **Web-Setup-Interface** – Konfiguration im Browser (keine Dateien bearbeiten)  
🔐 **Direkte 3CX REST API** – Keine CSV-Export mehr nötig  
🔒 **Sichere Credentials** – Passwort verschlüsselt gespeichert  
⚡ **Schneller Aufstart** – Setup in 2 Minuten  
📊 **Status-Dashboard** – Kontakt-Anzahl & letzte Sync live sehen  

---

## 📋 Vorbereitung

### 1. Was Sie brauchen:

- Linux-Server mit **Python 3.7+**
- 3CX-Telefonanlage (mit REST API)
- **Extension + Passwort** (Admin oder Systemeigentümer)
- 3CX **FQDN oder IP-Adresse** (z.B. `3cx.example.com` oder `192.168.1.10`)

### 2. Abhängigkeiten installieren:

```bash
sudo apt-get update
sudo apt-get install python3 python3-pip

pip install cryptography requests
```

---

## 🎯 Installation (5 Minuten)

### Schritt 1: Skript kopieren

```bash
sudo mkdir -p /opt/3cx_yealink_sync
sudo cp 3cx_yealink_sync_pro.py /opt/3cx_yealink_sync/
sudo chmod +x /opt/3cx_yealink_sync/3cx_yealink_sync_pro.py

# Benutzer
sudo useradd -r -s /bin/false 3cx_sync 2>/dev/null || true
sudo chown -R 3cx_sync:3cx_sync /opt/3cx_yealink_sync

# Ausgabeverzeichnis
sudo mkdir -p /var/www/html/phonebook
sudo chown 3cx_sync:3cx_sync /var/www/html/phonebook
```

### Schritt 2: Setup-Interface starten

```bash
# Temporär für Setup (wird durch Systemd ersetzt)
cd /opt/3cx_yealink_sync
python3 3cx_yealink_sync_pro.py --setup --port 8080
```

### Schritt 3: Browser öffnen

```
http://localhost:8080
```

Du siehst ein **Setup-Formular** mit 3 Feldern:

```
┌─────────────────────────────────────────────────────┐
│  3CX Setup                                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  3CX Hostname/FQDN                                  │
│  [                    3cx.example.com              │]│
│  FQDN oder IP-Adresse der 3CX-Anlage               │
│                                                     │
│  Nebenstelle (Extension)                            │
│  [                    101                          │]│
│  Ihre Admin-Nebenstelle (z.B. Systemowner)         │
│                                                     │
│  Passwort                                           │
│  [                    •••••••                      │]│
│  Wird verschlüsselt gespeichert                     │
│                                                     │
│  [ 🧪 Verbindung testen ]  [ 💾 Speichern & Start]│
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Schritt 4: Formular ausfüllen

| Feld | Beispiel | Beschreibung |
|------|----------|---|
| **FQDN** | `3cx.example.com` oder `192.168.1.50` | Hostname oder IP Ihrer 3CX-Anlage |
| **Extension** | `101` oder `102` | Eine Admin-Nebenstelle oder Systemeigentümer |
| **Passwort** | `mypassword123` | Passwort für diese Nebenstelle |

### Schritt 5: Testen & Speichern

1. **"🧪 Verbindung testen"** klicken
   - Prüft Erreichbarkeit & Login
   - Zeigt ✓ oder ✗

2. **"💾 Speichern & Starten"** klicken
   - Speichert Konfiguration verschlüsselt
   - Startet automatische Synchronisation

---

## 🔄 Automatischer Betrieb (Systemd)

### Service-Datei erstellen:

```bash
sudo tee /etc/systemd/system/3cx-yealink-sync.service > /dev/null <<'EOF'
[Unit]
Description=3CX → Yealink Phonebook Sync (PRO)
After=network.target

[Service]
Type=simple
User=3cx_sync
Group=3cx_sync
WorkingDirectory=/opt/3cx_yealink_sync

ExecStart=/usr/bin/python3 /opt/3cx_yealink_sync/3cx_yealink_sync_pro.py \
  --daemon \
  --config /opt/3cx_yealink_sync/config.json \
  --port 8080 \
  --interval 300

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=3cx-yealink-sync

[Install]
WantedBy=multi-user.target
EOF
```

### Service starten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable 3cx-yealink-sync.service
sudo systemctl start 3cx-yealink-sync.service

# Status prüfen
sudo systemctl status 3cx-yealink-sync.service

# Logs ansehen
sudo journalctl -u 3cx-yealink-sync.service -f
```

---

## 📱 Telefone konfigurieren

**Auf der Yealink AX83H/AX86R:**

1. **Admin-Oberfläche:** `http://<TELEFON_IP>`
2. **Directory** → **Local Phonebook**
3. **Remote Phonebook:**
   ```
   http://<SERVER_IP>:8080/phonebook.csv
   ```
4. **Refresh Interval:** `3600` (1 Stunde) oder beliebig
5. **Save** → **Reboot**

---

## 🎛️ Web-Interface verwenden

### Status anschauen

```
Browser: http://localhost:8080/status
```

JSON-Response:
```json
{
  "service": "running",
  "last_sync": "2026-08-19T10:45:32.123456",
  "contact_count": 487,
  "timestamp": "2026-08-19T10:47:15.654321",
  "mode": "api"
}
```

### Konfiguration ändern

```
Browser: http://localhost:8080
```

Neue Werte eingeben & "Speichern" klicken - sofort aktiv!

---

## ⚙️ Anpassungen

### Sync-Intervall ändern

Standard: **5 Minuten** (300 Sekunden)

In Systemd-Service ändern:
```bash
# Dann alle 30 Minuten:
--interval 1800
```

### Port ändern

```bash
# Statt Port 8080:
--port 9090
```

### Log-Datei

```bash
# In Systemd:
--log-file /var/log/3cx_yealink_sync.log
```

---

## 🧪 Testen ohne Systemd

```bash
# Setup starten (nur Setup, kein Sync)
python3 3cx_yealink_sync_pro.py --setup

# Daemon starten (mit Sync)
python3 3cx_yealink_sync_pro.py --daemon
```

---

## 🔐 Sicherheit

✅ **Passwort verschlüsselt** – Gespeichert mit Fernet (AES)  
✅ **Datei-Berechtigungen** – 3cx_sync Benutzer  
✅ **SSL-Unterstützung** – 3CX-API über HTTPS  
✅ **Self-Signed Certs OK** – Funktioniert mit 3CX-Standardzerts  

---

## 🆘 Häufige Probleme

### Problem: "Verbindungsfehler" beim Setup

**Ursache:** FQDN/IP nicht erreichbar

**Lösung:**
```bash
# Von Server aus testen:
ping 3cx.example.com
curl -k https://3cx.example.com/api/v1/ping
```

### Problem: "Login fehlgeschlagen"

**Ursache:** Extension oder Passwort falsch

**Lösung:**
- Prüfe Extension & Passwort in 3CX Admin Console
- Benutzer muss "Systemowner" oder Admin-Rechte haben

### Problem: "Keine Kontakte werden synchronisiert"

**Lösung:**
```bash
# Logs prüfen:
sudo journalctl -u 3cx-yealink-sync.service -n 50

# Status API:
curl http://localhost:8080/status

# Datei-Logs:
tail -f /var/log/3cx_yealink_sync.log
```

### Problem: Port 8080 schon in Benutzung

```bash
# Anderer Port:
python3 3cx_yealink_sync_pro.py --setup --port 9090
```

---

## 📊 Was das System macht

```
3CX-Telefonanlage
       ↓
   (REST API)
       ↓
Linux-Server (3cx_yealink_sync_pro.py)
       ├─ Liest Kontakte über REST API
       ├─ Konvertiert zu Yealink-Format
       ├─ Speichert phonebook.csv & .xml
       │
HTTP-Server (Port 8080)
       ├─ /               (Setup-Interface)
       ├─ /phonebook.csv  (für Telefone)
       ├─ /phonebook.xml  (Alternative)
       └─ /status         (Status-API)
       ↓
Yealink AX83H/AX86R
       └─ Laden & zeigen Kontakte
```

---

## 📚 Vollständige Dokumentation

Für Details, Troubleshooting & erweiterte Konfiguration:

→ **INSTALLATIONSANLEITUNG.md** (Fallback für CSV-Modus)  
→ Quellcode **3cx_yealink_sync_pro.py** (gut kommentiert)

---

## ✅ Fertig!

**Das System ist jetzt:**
- ✓ Konfiguriert über Web-Interface
- ✓ Lädt Kontakte direkt aus 3CX
- ✓ Synchronisiert automatisch alle 5 Minuten
- ✓ Stellt CSV & XML für Telefone bereit

**Nächster Schritt:**
→ Yealink-Telefone konfigurieren (siehe oben: "Telefone konfigurieren")

---

**Version:** 1.0 PRO | **Datum:** 2026-08-19  
**Für:** Yealink AX83H/AX86R + 3CX mit REST API
