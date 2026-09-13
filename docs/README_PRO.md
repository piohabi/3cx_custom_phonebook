# 3CX ↔ Yealink AX Phonebook Sync

**Automatische Synchronisation mit Web-Setup & direkter 3CX-API Integration**

---

## 🎯 Welche Version passt zu mir?

### 📋 **STANDARD Version** (`3cx_yealink_sync.py`)

Für: **CSV-basierte Synchronisation**

- Datenquelle: Manueller oder automatisierter **3CX-CSV-Export**
- Konfiguration: Kommandozeile / Skript-Parameter
- Setup: Technisch (Datei-Pfade anpassen)
- Ideal für: Automatisierte Pipelines, bestehende Infra

**Dateien:**
```
3cx_yealink_sync.py          (Hauptskript)
3cx-yealink-sync.service      (Systemd-Service)
INSTALLATIONSANLEITUNG.md     (Detaillierte Docs)
QUICK_START.md                (Schnelleinstieg)
```

---

### ⭐ **PRO Version** (`3cx_yealink_sync_pro.py`)

Für: **Direkte 3CX-API + Web-Setup Interface**

- Datenquelle: **Direkt aus 3CX REST API** (keine CSV nötig)
- Konfiguration: **Web-Browser Interface** (grafisch)
- Setup: **2 Minuten**, keine technischen Skills nötig
- Ideal für: Schnelle Einrichtung, Endbenutzer-Konfiguration

**Features:**
```
✨ Web-Setup-Interface (http://localhost:8080)
🔐 Sichere Credential-Speicherung (verschlüsselt)
⚡ Direkte 3CX REST API (schneller, live)
📊 Status-Dashboard & API
🔄 Automatische Kontakt-Synchronisation
```

**Dateien:**
```
3cx_yealink_sync_pro.py              (Hauptskript PRO)
3cx-yealink-sync-pro.service         (Systemd-Service PRO)
PRO_QUICKSTART.md                    (Schnelleinstieg PRO)
```

---

## 🚀 Schnellstart: Welche Version installiere ich?

### Szenario A: "Ich will schnell starten, ohne zu programmieren"
→ **PRO Version** nutzen!

```bash
# Installation
sudo cp 3cx_yealink_sync_pro.py /opt/3cx_yealink_sync/
python3 3cx_yealink_sync_pro.py --setup

# Browser öffnen: http://localhost:8080
# Formular ausfüllen & speichern
# Fertig!
```

Zeitaufwand: **5-10 Minuten** ✓

---

### Szenario B: "Ich habe bereits einen CSV-Export-Prozess"
→ **STANDARD Version** nutzen!

```bash
# Installation
sudo cp 3cx_yealink_sync.py /opt/3cx_yealink_sync/
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --daemon
```

Zeitaufwand: **10-15 Minuten** ✓

---

### Szenario C: "Ich will beide testen"
→ **Beide installieren** (auf verschiedenen Ports)

```bash
# Standard-Version auf Port 8080
python3 3cx_yealink_sync.py --port 8080

# PRO-Version auf Port 9090
python3 3cx_yealink_sync_pro.py --port 9090
```

---

## 📊 Feature-Vergleich

| Feature | STANDARD | PRO |
|---------|----------|-----|
| **Datenquelle** | CSV-Datei | 3CX REST API |
| **Setup-Zeit** | 15 min | 5 min |
| **Web-Interface** | ❌ | ✅ |
| **Kommandozeile-Config** | ✅ | ✅ |
| **Encrypted Passwords** | ❌ | ✅ |
| **Status-Dashboard** | ✅ | ✅ |
| **CSV & XML Output** | ✅ | ✅ |
| **Systemd-Service** | ✅ | ✅ |
| **Auto-Kontakt-Sync** | ✅ | ✅ |
| **Komplexität** | Mittel | Niedrig |
| **Anforderungen** | Python 3 | Python 3 + cryptography + requests |

---

## 🎯 PRO-Version: Wie funktioniert sie?

### Architektur:

```
1. Setup-Phase (einmalig)
   ┌─────────────────────────────────┐
   │ Browser öffnet http://localhost:8080
   │ Webformular anzeigen
   │ Eingabe: FQDN, Extension, Passwort
   │ "Verbindung testen" → 3CX Login prüfen
   │ "Speichern" → Config verschlüsselt ablegen
   └─────────────────────────────────┘

2. Daemon-Phase (automatisch)
   ┌─────────────────────────────────┐
   │ Systemd-Service läuft im Hintergrund
   │ Alle 5 Minuten:
   │ - Login bei 3CX über REST API
   │ - Phonebook-Kontakte abrufen
   │ - In Yealink-Format konvertieren
   │ - phonebook.csv & .xml generieren
   │ - HTTP-Server serviert Dateien
   └─────────────────────────────────┘

3. Status & Monitoring
   ┌─────────────────────────────────┐
   │ http://localhost:8080/status
   │ JSON mit: last_sync, contact_count, etc.
   └─────────────────────────────────┘
```

### Sicherheit:

- **Passwort-Verschlüsselung**: AES (Fernet)
- **Secure Credentials**: In JSON-Datei verschlüsselt
- **HTTPS-Support**: 3CX-API über HTTPS
- **Berechtigungen**: 3cx_sync Benutzer (no root)

---

## 🔑 3CX-Anforderungen

### Welche Extension verwenden?

1. **Admin-Extension** (z.B. 101)
   - Voller Zugriff
   - Empfohlen für Systemowner

2. **Systemeigentümer-Extension**
   - Hat Zugriff auf Phonebook
   - Optimal für diesen Use-Case

3. **Normale Benutzer-Extension**
   - Funktioniert NICHT (keine Phonebook-API-Rechte)

### Wie finde ich meine Extension?

```
3CX Admin Console → Accounts → Suche nach dir
oder
Telefon-Einstellung → Status → Extension anzeigen
```

---

## 📱 Telefone konfigurieren (beide Versionen gleich)

### Yealink AX83H/AX86R:

1. **Admin-Interface öffnen:**
   ```
   http://<TELEFON_IP>
   Benutzername: admin
   Passwort: (Standard oder custom)
   ```

2. **Directory** → **Local Phonebook**

3. **Remote Phonebook URL:**
   ```
   http://<SERVER_IP>:8080/phonebook.csv
   ```

4. **Refresh Interval:**
   ```
   3600  (1x pro Stunde)
   300   (1x pro 5 Minuten - wenn häufige Änderungen)
   ```

5. **Save** → **Reboot**

### Über 3CX-Provisioning (empfohlen):

```
3CX Admin Console
  → Hardware Phones
    → Phone Templates
      → AX83H-Template
        → Remote Phonebook URL:
           http://<SERVER_IP>:8080/phonebook.csv
        → Save
```

Alle Telefone laden dann automatisch das Update!

---

## 🧪 Test-Szenarios

### PRO-Version testen (ohne Systemd):

```bash
# 1. Setup-Interface nur starten
python3 3cx_yealink_sync_pro.py --setup

# 2. Konfiguration eingeben & speichern
# (Browser öffnet: http://localhost:8080)

# 3. Daemon testen (mit Sync)
python3 3cx_yealink_sync_pro.py --daemon

# 4. Logs anschauen
tail -f /var/log/3cx_yealink_sync.log

# 5. Status prüfen
curl http://localhost:8080/status | jq
```

### STANDARD-Version testen:

```bash
# 1. Einmalige Sync
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --once

# 2. CSV-Export prüfen
ls -la /var/www/html/phonebook/
```

---

## ⚙️ Konfigurationsverwaltung

### PRO-Version: Web-Interface

```
Browser: http://localhost:8080
├─ FQDN eingeben
├─ Extension eingeben
├─ Passwort eingeben
├─ "Verbindung testen" klicken
└─ "Speichern" klicken
→ Config wird verschlüsselt in /opt/3cx_yealink_sync/config.json gespeichert
```

### PRO-Version: Konfiguration anpassen

```bash
# Systemd-Service bearbeiten:
sudo systemctl edit 3cx-yealink-sync.service

# Änderungen im [Service] Abschnitt:
# --port 9090       (anderer Port)
# --interval 600    (10 Minuten Sync-Intervall)

# Neu laden:
sudo systemctl daemon-reload
sudo systemctl restart 3cx-yealink-sync.service
```

### STANDARD-Version: Kommandozeile

```bash
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --interval 300 \
  --port 8080 \
  --daemon
```

---

## 🐛 Troubleshooting

### PRO-Version: "Verbindung fehlgeschlagen"

```bash
# 1. 3CX erreichbar?
ping 3cx.example.com
curl -k https://3cx.example.com/api/v1/ping

# 2. Extension & Passwort korrekt?
# (Im Setup-Interface "Testen" klicken)

# 3. Logs prüfen:
sudo journalctl -u 3cx-yealink-sync.service -n 50
```

### STANDARD-Version: "CSV nicht gefunden"

```bash
# 1. CSV existiert?
ls -la /var/lib/3cx/phonebook/contacts_3cx.csv

# 2. CSV-Export aus 3CX durchführen:
# (3CX Admin Console → Phonebook → Export)

# 3. CSV-Pfad in Systemd-Service prüfen
sudo systemctl cat 3cx-yealink-sync.service
```

### Beide: "Telefone zeigen keine Kontakte"

```bash
# 1. HTTP-Server läuft?
curl http://localhost:8080/phonebook.csv

# 2. Kontakte vorhanden?
wc -l /var/www/html/phonebook/phonebook.csv
# (Sollte > 2 sein: 1 Header + Kontakte)

# 3. Telefon-URL korrekt?
# Prüfe: Directory → Local Phonebook → URL
# Sollte sein: http://<SERVER_IP>:8080/phonebook.csv
```

---

## 📚 Dokumentation

### PRO-Version:
- **PRO_QUICKSTART.md** – Schnelleinstieg (5-10 min)
- **3cx_yealink_sync_pro.py** – Quellcode (gut kommentiert)

### STANDARD-Version:
- **QUICK_START.md** – Schnelleinstieg
- **INSTALLATIONSANLEITUNG.md** – Detaillierte Anleitung
- **3cx_yealink_sync.py** – Quellcode

---

## 🔄 Von STANDARD zu PRO wechseln

Falls Sie zuerst STANDARD haben und auf PRO wechseln möchten:

```bash
# Alte Version stoppen
sudo systemctl stop 3cx-yealink-sync.service

# Neue Version installieren
sudo cp 3cx_yealink_sync_pro.py /opt/3cx_yealink_sync/
sudo cp 3cx-yealink-sync-pro.service /etc/systemd/system/

# Setup starten
python3 3cx_yealink_sync_pro.py --setup

# Neue Service aktivieren
sudo systemctl daemon-reload
sudo systemctl enable --now 3cx-yealink-sync-pro.service

# Alte Service deaktiviegen
sudo systemctl disable 3cx-yealink-sync.service
```

**CSV-Konfiguration wird nicht mehr gebraucht!** ✓

---

## ✅ Checkliste vor Produktiveinsatz

- [ ] Richtige Version gewählt (STANDARD oder PRO)
- [ ] Python 3.7+ installiert
- [ ] Abhängigkeiten installiert (requests, cryptography für PRO)
- [ ] 3CX erreichbar (FQDN/IP korrekt)
- [ ] Extension & Passwort funktionieren
- [ ] Test durchgeführt (`--setup` oder `--once`)
- [ ] Systemd-Service installiert
- [ ] Service läuft (`systemctl status`)
- [ ] HTTP-Server antwortet (`curl http://localhost:8080/status`)
- [ ] Telefone konfiguriert (Remote Phonebook URL)
- [ ] Kontakte auf Telefon sichtbar

---

## 🎯 Support

- **Fragen?** → Siehe Dokumentation (PRO_QUICKSTART.md oder QUICK_START.md)
- **Bug-Report?** → Prüfe Logs: `journalctl -u 3cx-yealink-sync*.service`
- **Fehler beim Setup?** → Führe Test aus: "Verbindung testen"

---

**Version:** 2.0 (STANDARD + PRO)  
**Datum:** 2026-08-19  
**Für:** Yealink AX83H/AX86R + 3CX auf Linux

---

**Entscheidung treffen? →**
- 🚀 **Schnell & einfach?** → PRO (Web-Interface)
- 📋 **CSV-Pipeline vorhanden?** → STANDARD (CLI)
- ❓ **Unsicher?** → PRO (einfacher)

Viel Erfolg! 🎉
