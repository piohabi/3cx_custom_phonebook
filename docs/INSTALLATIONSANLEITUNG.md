# 3CX → Yealink AX Series Phonebook Sync Service

Installationsanleitung für Linux-Server (Debian/Ubuntu/CentOS)

---

## 📋 Inhalt

1. [Anforderungen](#anforderungen)
2. [Installation](#installation)
3. [Konfiguration](#konfiguration)
4. [Als Systemd-Service einrichten](#als-systemd-service-einrichten)
5. [Yealink-Telefone konfigurieren](#yealink-telefone-konfigurieren)
6. [Status & Monitoring](#status--monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Anforderungen

- **Linux-Server** (Debian 11+, Ubuntu 20.04+, CentOS 8+)
- **Python 3.7+** (prüfen: `python3 --version`)
- **Webserver** (nginx oder Apache, optional – das Skript bringt einen HTTP-Server mit)
- **3CX-CSV-Export** des Firmentelefonbuchs (als Datei oder periodischer Export)

---

## Installation

### Schritt 1: Skript auf den Server kopieren

```bash
# Verzeichnis erstellen
sudo mkdir -p /opt/3cx_yealink_sync
cd /opt/3cx_yealink_sync

# Skript kopieren (z.B. von deinem Admin-PC)
# scp 3cx_yealink_sync.py root@<SERVER_IP>:/opt/3cx_yealink_sync/
# ODER: Datei manuell kopieren

# Skript ausführbar machen
sudo chmod +x 3cx_yealink_sync.py

# Eigentümer setzen (optional, z.B. ein Benutzer "3cx_sync")
sudo useradd -r -s /bin/false 3cx_sync 2>/dev/null || true
sudo chown -R 3cx_sync:3cx_sync /opt/3cx_yealink_sync
```

### Schritt 2: Ausgabeverzeichnis vorbereiten

```bash
# Verzeichnis für CSV/XML erstellen
sudo mkdir -p /var/www/html/phonebook
sudo chown 3cx_sync:3cx_sync /var/www/html/phonebook
sudo chmod 755 /var/www/html/phonebook
```

### Schritt 3: 3CX-CSV regelmäßig exportieren

Die **3CX-CSV muss regelmäßig** auf dem Server bereitgestellt werden. Zwei Optionen:

#### Option A: Manueller Export (einfach, nicht automatisiert)
1. In 3CX-Adminoberfläche: **Phonebook** → **Export as CSV**
2. Die Datei auf den Server kopieren: `/var/lib/3cx/phonebook/contacts_3cx.csv`

#### Option B: Automatischer Export (empfohlen)

Cron-Job auf 3CX-Server (falls 3CX auf Windows läuft, nutze Task Scheduler):

```bash
# Beispiel: Export alle 30 Minuten
# crontab -e (als root auf 3CX-Server)

*/30 * * * * /usr/bin/3cx --export-phonebook /var/lib/3cx/phonebook/contacts_3cx.csv
```

Oder über 3CX-API:
```bash
#!/bin/bash
# 3cx_export_phonebook.sh

CSV_PATH="/var/lib/3cx/phonebook/contacts_3cx.csv"

# CSV von 3CX exportieren (Beispiel, je nach 3CX-Version unterschiedlich)
curl -s -u admin:PASSWORT "https://3cx.example.com/api/phonebook/export" \
  > "$CSV_PATH"

echo "$(date): CSV exportiert nach $CSV_PATH" >> /var/log/3cx_export.log
```

**Wichtig:** Die CSV muss diese Spalten enthalten:
```
FirstName,LastName,Company,Mobile,Mobile2,Business,Business2,Home,Other,BusinessFax,Pager,Email
```

---

## Konfiguration

### Schnelltest (einmalige Ausführung)

```bash
cd /opt/3cx_yealink_sync

# Einmalige Synchronisation (Test)
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --once

# Überprüfen, ob CSV/XML erstellt wurden:
ls -la /var/www/html/phonebook/
```

Wenn es funktioniert, solltest du sehen:
```
-rw-r--r-- 1 3cx_sync 3cx_sync  45K Aug 19 10:30 phonebook.csv
-rw-r--r-- 1 3cx_sync 3cx_sync  52K Aug 19 10:30 phonebook.xml
```

---

## Als Systemd-Service einrichten

### Schritt 1: Service-Datei erstellen

```bash
sudo tee /etc/systemd/system/3cx-yealink-sync.service > /dev/null <<'EOF'
[Unit]
Description=3CX → Yealink AX Phonebook Sync Service
After=network.target
Documentation=https://example.com/3cx-yealink-sync

[Service]
Type=simple
User=3cx_sync
Group=3cx_sync

# Hauptbefehl
ExecStart=/usr/bin/python3 /opt/3cx_yealink_sync/3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --interval 300 \
  --port 8080 \
  --log-file /var/log/3cx_yealink_sync.log

# Neu starten bei Fehler
Restart=always
RestartSec=10

# Prozess-Management
KillMode=process
KillSignal=SIGINT

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=3cx-yealink-sync

[Install]
WantedBy=multi-user.target
EOF
```

### Schritt 2: Service aktivieren und starten

```bash
# Service-Datei laden
sudo systemctl daemon-reload

# Service aktivieren (startet beim Boot)
sudo systemctl enable 3cx-yealink-sync.service

# Service starten
sudo systemctl start 3cx-yealink-sync.service

# Status prüfen
sudo systemctl status 3cx-yealink-sync.service
```

### Schritt 3: Logs überwachen

```bash
# Live-Logs ansehen (30 Sekunden lang)
sudo journalctl -u 3cx-yealink-sync.service -f --lines=50

# Oder Datei-Log lesen:
tail -f /var/log/3cx_yealink_sync.log
```

---

## Yealink-Telefone konfigurieren

### Auf der Yealink AX83H/AX86R:

1. **Admin-Oberfläche öffnen** (Browser: `http://<TELEFON_IP>`)
   - Benutzername: `admin`
   - Passwort: (Standardpasswort oder dein Admin-Passwort)

2. **Directory → Local Phonebook**

3. **Remote Phonebook (HTTP):**
   - **URL**: `http://<SERVER_IP>:8080/phonebook.csv`
   - (oder `.xml`, je nach Telefonmodell)
   - **Refresh Interval**: z.B. 3600 (Sekunden) = 1x pro Stunde

4. **Speichern und Phone neu starten**

5. **Testen:**
   - Auf dem Telefon: **Directory** öffnen
   - Kontakte sollten mit **allen 4 Nummernfeldern** sichtbar sein:
     - Office (Geschäftlich)
     - Mobile (Mobil)
     - Other (Sonstige)
     - BusinessFax (Fax)

### Alternativ: Über 3CX-Provisioning-Template

Wenn alle AX83H-Telefone über 3CX provisioniert werden:

1. In **3CX Admin Console**: **Hardware Phones → Phone Templates**
2. AX83H-Template wählen
3. **Remote Phonebook URL** hinzufügen:
   ```
   http://<SERVER_IP>:8080/phonebook.csv
   ```
4. **Speichern**

Alle neuen/aktualisierten Telefone laden dann automatisch das Phonebook.

---

## Status & Monitoring

### Web-Interface

Öffne im Browser:
```
http://<SERVER_IP>:8080/
```

Du siehst:
- Links zu `phonebook.csv` und `phonebook.xml`
- Link zu `/status` für JSON-Statusinfo

### Status-API

```bash
# JSON-Antwort mit aktuellem Status
curl http://<SERVER_IP>:8080/status | jq

# Beispiel-Antwort:
{
  "service": "running",
  "last_sync": "2026-08-19T10:45:32.123456",
  "contact_count": 487,
  "timestamp": "2026-08-19T10:47:15.654321"
}
```

### Service überwachen

```bash
# Ist der Service am Laufen?
sudo systemctl is-active 3cx-yealink-sync.service

# Service neustarten (z.B. nach CSV-Änderung)
sudo systemctl restart 3cx-yealink-sync.service

# Service stoppen
sudo systemctl stop 3cx-yealink-sync.service

# Logs der letzten 100 Zeilen
sudo journalctl -u 3cx-yealink-sync.service -n 100
```

---

## Troubleshooting

### Problem 1: "CSV-Datei nicht gefunden"

```
[ERROR] CSV-Datei nicht gefunden: /var/lib/3cx/phonebook/contacts_3cx.csv
```

**Lösung:**
- Prüfe, ob der CSV-Export aus 3CX funktioniert
- Prüfe den Pfad: `ls -la /var/lib/3cx/phonebook/`
- Starte den Export in 3CX manuell

### Problem 2: "Keine Kontakte geladen"

```
[WARNING] Keine Kontakte geladen!
```

**Ursachen & Lösungen:**
- CSV ist leer → Kontakte in 3CX hinzufügen
- CSV-Header falsch → Header muss enthalten: `FirstName,LastName,Company,Mobile,Mobile2,Business,Business2,Home,Other,BusinessFax,Pager,Email`
- CSV-Kodierung falsch → Muss UTF-8 sein: 
  ```bash
  file /var/lib/3cx/phonebook/contacts_3cx.csv
  iconv -f ISO-8859-1 -t UTF-8 contacts_3cx.csv > contacts_3cx_utf8.csv
  ```

### Problem 3: HTTP-Server antwortet nicht

```bash
# Port 8080 gebunden?
sudo lsof -i :8080
# Oder:
sudo netstat -tlnp | grep 8080

# Falls Port belegt, anderer Port nutzen:
sudo systemctl stop 3cx-yealink-sync.service
# Systemd-Service bearbeiten:
sudo systemctl edit 3cx-yealink-sync.service
# --port 8080 zu --port 9090 ändern
sudo systemctl start 3cx-yealink-sync.service
```

### Problem 4: Telefon lädt Phonebook nicht

```bash
# Prüfe Netzwerkerreichbarkeit vom Telefon:
# (im Telefon-Weboberfläche: Diagnose/Debug)

# Von Server aus Test:
curl -v http://localhost:8080/phonebook.csv

# Firewall blockiert Port?
sudo ufw allow 8080/tcp
# Oder:
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

### Problem 5: Service stoppt immer wieder

```bash
# Logs detailliert ansehen:
sudo journalctl -u 3cx-yealink-sync.service -p err

# Service im Foreground debuggen:
cd /opt/3cx_yealink_sync
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --log-file /tmp/debug.log
```

---

## 🎯 Häufige Fragen

### F: Welche Nummernfelder werden unterstützt?

**A:** Das Skript mappt intelligent:
- **office_number**: Business (primär) oder Business2 (fallback)
- **mobile_number**: Mobile
- **other_number**: Mobile2 oder Home (fallback)
- **businessFax**: BusinessFax oder Other (fallback)

Alle 4 Felder der AX83H werden genutzt, wenn verfügbar.

### F: Wie oft wird synchronisiert?

**A:** Standard ist alle **5 Minuten** (300 Sekunden). Änderbar mit `--interval`:
```bash
--interval 60    # Jede Minute (schneller)
--interval 1800  # Alle 30 Minuten (sparsam)
```

### F: Kann ich CSV und XML parallel nutzen?

**A:** Ja! Das Skript erzeugt **immer beide Formate**. Telefone können beliebig csv oder xml laden.

### F: Funktioniert es auch mit anderen Telefonen (Snom, Gigaset)?

**A:** Das CSV-Format ist Standard – funktioniert mit den meisten VoIP-Telefonen. XML ist Yealink-spezifisch. Teste mit deinem Telefonmodell.

### F: Kann ich das Skript im Docker laufen lassen?

**A:** Ja, einfach ein Dockerfile bauen:
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl
COPY 3cx_yealink_sync.py /app/
WORKDIR /app
CMD ["python3", "3cx_yealink_sync.py", "--input", "/data/contacts.csv", "--output", "/output"]
```

---

## Support & Logs

Alle Logs landen in:
- **Systemd**: `journalctl -u 3cx-yealink-sync.service`
- **Datei**: `/var/log/3cx_yealink_sync.log` (falls `--log-file` gesetzt)

Bei Problemen: Log aus dem letzten Lauf posten (sensible Daten entfernen):
```bash
sudo journalctl -u 3cx-yealink-sync.service --since "2 hours ago" | head -100
```

---

**Version**: 1.0 | **Datum**: 2026-08-19 | **Für**: Yealink AX83H/AX86R + 3CX
