# 🚀 Quick Start: 3CX → Yealink AX Phonebook Sync

**In 10 Minuten produktiv!**

---

## Schritt-für-Schritt (Copy & Paste)

### 1️⃣ Skript-Installation (auf Linux-Server)

```bash
# Als root oder mit sudo

# Verzeichnis
sudo mkdir -p /opt/3cx_yealink_sync
cd /opt/3cx_yealink_sync

# Skript herunterladen oder copy-pasten
# (Download-Link oder Dateiinhalt hier einfügen)

sudo chmod +x 3cx_yealink_sync.py

# Benutzer für Service erstellen
sudo useradd -r -s /bin/false 3cx_sync 2>/dev/null || true
sudo chown -R 3cx_sync:3cx_sync /opt/3cx_yealink_sync
```

### 2️⃣ Ausgabeverzeichnis

```bash
sudo mkdir -p /var/www/html/phonebook
sudo chown 3cx_sync:3cx_sync /var/www/html/phonebook
sudo chmod 755 /var/www/html/phonebook
```

### 3️⃣ Erste Synchronisation testen

```bash
cd /opt/3cx_yealink_sync

# CSV-Datei muss existieren! (von 3CX exportiert)
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --once
```

**Wenn erfolgreich:**
```
✓ 123 Kontakte aus contacts_3cx.csv gelesen
✓ CSV geschrieben: /var/www/html/phonebook/phonebook.csv
✓ XML geschrieben: /var/www/html/phonebook/phonebook.xml
✓ Sync erfolgreich: 123 Kontakte verarbeitet
```

### 4️⃣ Systemd-Service installieren

```bash
# Service-Datei kopieren
sudo cp 3cx-yealink-sync.service /etc/systemd/system/

# Service laden
sudo systemctl daemon-reload

# Service starten
sudo systemctl start 3cx-yealink-sync.service

# Aktivieren (Auto-Start beim Reboot)
sudo systemctl enable 3cx-yealink-sync.service

# Status prüfen
sudo systemctl status 3cx-yealink-sync.service
```

### 5️⃣ Logs überwachen

```bash
# Live-Logs
sudo journalctl -u 3cx-yealink-sync.service -f

# (Ctrl+C zum Beenden)
```

### 6️⃣ Telefone konfigurieren

**Yealink AX83H/AX86R Admin-Interface:**

1. Browser: `http://<TELEFON_IP>` (Admin-Login)
2. **Directory** → **Local Phonebook**
3. **Remote Phonebook URL:**
   ```
   http://<SERVER_IP>:8080/phonebook.csv
   ```
4. **Refresh Interval:** `3600` (1 Stunde) oder beliebig
5. **Save** → **Telefon neustarten**

### 7️⃣ Testen

```bash
# Browser oder curl:
curl http://<SERVER_IP>:8080/status | jq

# Sollte zeigen:
# {
#   "service": "running",
#   "contact_count": 123,
#   "last_sync": "2026-08-19T..."
# }
```

---

## ⚠️ Wichtig: 3CX-CSV

Die CSV **muss regelmäßig** von 3CX exportiert werden:

### Optionen:

**A) Manuell exportieren (in 3CX Admin):**
- **Phonebook** → **Export as CSV**
- Speichern nach: `/var/lib/3cx/phonebook/contacts_3cx.csv`

**B) Automatisch via Cron (auf 3CX-Server):**
```bash
# Alle 30 Minuten exportieren
*/30 * * * * /path/to/export-3cx-phonebook.sh
```

Script-Beispiel:
```bash
#!/bin/bash
# Pfad zur 3CX-CLI oder Datenbank anpassen!
# 3CX muss eine Export-Funktion/API haben

CSV_PATH="/var/lib/3cx/phonebook/contacts_3cx.csv"
# ... 3CX-Export-Command hier ...
```

---

## 🔗 Netzwerk

```
3CX Server (CSV exportiert)
       ↓
Linux Server (3cx_yealink_sync.py läuft hier)
       ↓
HTTP://SERVER_IP:8080/phonebook.csv
       ↓
Yealink AX83H (lädt & zeigt Kontakte)
```

---

## 📋 Checkliste

- [ ] Skript auf Server kopiert
- [ ] `3cx_sync` Benutzer erstellt
- [ ] CSV von 3CX exportiert
- [ ] Erster Test erfolgreich (`--once`)
- [ ] Service-Datei installiert
- [ ] Service läuft (`systemctl status`)
- [ ] Yealink konfiguriert (Remote URL)
- [ ] Telefon zeigt Kontakte mit 4 Feldern

---

## 📞 Kontakt-Felder auf AX83H

| Yealink-Feld   | 3CX-Quelle     | Fallback           |
|---|---|---|
| **Office**     | `Business`     | `Business2`        |
| **Mobile**     | `Mobile`       | (leer)             |
| **Other**      | `Mobile2`      | `Home`             |
| **Fax**        | `BusinessFax`  | `Other`            |

---

## 🆘 Schnell-Debugging

```bash
# 1. Service läuft?
sudo systemctl is-active 3cx-yealink-sync.service

# 2. Port 8080 erreichbar?
curl -v http://localhost:8080/

# 3. CSV-Datei existiert?
ls -la /var/lib/3cx/phonebook/contacts_3cx.csv

# 4. Ausgabedateien erstellt?
ls -la /var/www/html/phonebook/

# 5. Logs ansehen?
sudo journalctl -u 3cx-yealink-sync.service -n 50
```

---

## 📚 Vollständige Dokumentation

Siehe: **INSTALLATIONSANLEITUNG.md**

---

**Status:** Bereit zum Produktiveinsatz ✅
