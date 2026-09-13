# 3CX ↔ Yealink AX Phonebook Sync Service

**Automatische Synchronisation des 3CX-Kontaktbuchs mit Yealink AX83H/AX86R Telefonen**

---

## 📦 Was ist in diesem Paket?

| Datei | Beschreibung |
|-------|---|
| **3cx_yealink_sync.py** | Haupt-Sync-Skript (Python 3) – Das Herzstück |
| **3cx-yealink-sync.service** | Systemd-Service-Datei (Linux) |
| **INSTALLATIONSANLEITUNG.md** | Detaillierte Setup-Anleitung (DE) |
| **QUICK_START.md** | Schnelleinstieg – 10 Minuten bis produktiv |
| **test_3cx_yealink_sync.sh** | Test- & Diagnose-Skript |
| **README.md** | Diese Datei |

---

## 🎯 Was macht dieses System?

```
3CX-Telefonanlage
       │
       ├─ Firmentelefonbuch exportiert als CSV
       │
3CX-Server (/var/lib/3cx/phonebook/contacts_3cx.csv)
       │
       ↓
Linux-Server läuft 3cx_yealink_sync.py
       │
       ├─ Liest CSV jede 5 Minuten
       ├─ Konvertiert in Yealink AX Format
       ├─ Speichert als phonebook.csv & phonebook.xml
       │
       ↓
HTTP-Server (Port 8080)
       │
       ├─ http://SERVER_IP:8080/phonebook.csv
       │
Yealink AX83H/AX86R Telefone
       │
       └─ Laden & zeigen Kontakte mit allen 4 Feldern:
           • Office (Geschäftlich)
           • Mobile (Mobil)
           • Other (Sonstige)
           • BusinessFax (Fax)
```

---

## 🚀 Schnellstart

**Für Eilige:**

```bash
# 1. Auf Linux-Server (als root)
cd /tmp
mkdir -p /opt/3cx_yealink_sync
cp 3cx_yealink_sync.py /opt/3cx_yealink_sync/
chmod +x /opt/3cx_yealink_sync/3cx_yealink_sync.py

# 2. Benutzer erstellen
useradd -r -s /bin/false 3cx_sync 2>/dev/null || true

# 3. Ausgabe-Verzeichnis
mkdir -p /var/www/html/phonebook
chown 3cx_sync:3cx_sync /var/www/html/phonebook

# 4. Test (mit CSV von 3CX)
cd /opt/3cx_yealink_sync
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --once

# 5. Service installieren & starten
cp 3cx-yealink-sync.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now 3cx-yealink-sync.service

# 6. Status prüfen
systemctl status 3cx-yealink-sync.service
```

**Für Details: Siehe [QUICK_START.md](QUICK_START.md)**

---

## 📋 Anforderungen

- **Linux-Server** (Debian 11+, Ubuntu 20.04+, CentOS 8+)
- **Python 3.7+** (fast überall vorhanden)
- **3CX mit CSV-Export** des Firmentelefonbuchs
- **Yealink AX83H oder AX86R** (oder kompatible Modelle)
- **Netzwerk-Erreichbarkeit** zwischen Server und Telefonen

---

## 🔧 Installation

### Ausführliche Anleitung
👉 **[INSTALLATIONSANLEITUNG.md](INSTALLATIONSANLEITUNG.md)** (Deutsch, 200+ Zeilen)

### Kurzversion
👉 **[QUICK_START.md](QUICK_START.md)** (5-10 Minuten Setup)

---

## 📝 Das macht das Skript

### Automatische Kontakt-Konvertierung

**Eingabe** (3CX-CSV):
```csv
FirstName,LastName,Company,Mobile,Mobile2,Business,Business2,Home,Other,BusinessFax,Pager,Email
Max,Mustermann,Musterfirma GmbH,01234567890,0171999999,02315555555,,,,02314444444,,max@musterfirma.de
```

**Ausgabe** (Yealink AX Format):
```csv
display_name,office_number,mobile_number,other_number,businessFax,line,ring,auto_divert,priority,group_id_name,default_photo,photo_data
"Musterfirma GmbH",02315555555,01234567890,0171999999,02314444444,-1,Auto,,,All Contacts,Default:default_contact_image.png,
```

**Im Telefon sichtbar als:**
- **Office**: 02315555555 (Business)
- **Mobile**: 01234567890 (Mobile)
- **Other**: 0171999999 (Mobile2)
- **Fax**: 02314444444 (BusinessFax)

### Automatische Synchronisation
- Lädt die 3CX-CSV **automatisch alle 5 Minuten** (konfigurierbar)
- Konvertiert Kontakte
- Stellt CSV & XML via HTTP bereit
- Läuft als **Systemd-Service** (Auto-Restart bei Fehlern)

### HTTP-Interface
```
http://SERVER_IP:8080/
├── phonebook.csv       (für Yealink-Telefone)
├── phonebook.xml       (Alternativ, VP-Contact-Format)
└── status              (JSON API für Monitoring)
```

---

## 💡 Features

✅ **Intelligent Mapping** – Fallback-Logik für alle Felder  
✅ **4 Nummernfelder** – Office, Mobile, Other, Fax  
✅ **CSV + XML** – Beide Formate gleichzeitig  
✅ **Robuster Betrieb** – Systemd-Service mit Auto-Restart  
✅ **HTTP-Server** – Remote-Phonebook-Link für Telefone  
✅ **Logging** – Detaillierte Logs zu Systemd + Datei  
✅ **Status-API** – JSON-API für Monitoring  
✅ **Konfigurierbar** – Port, Intervall, Formate anpassbar  
✅ **Fehlerbehandlung** – Graceful Degradation bei Problemen  

---

## 🔌 Telefone konfigurieren

### Yealink AX83H/AX86R

1. **Admin-Interface**: `http://<TELEFON_IP>` (Admin-Login)
2. **Directory** → **Local Phonebook**
3. **Remote Phonebook URL**: 
   ```
   http://<SERVER_IP>:8080/phonebook.csv
   ```
4. **Refresh Interval**: `3600` (Sekunden) oder beliebig
5. **Save** → **Reboot**

### Über 3CX-Provisioning (recommended)

1. 3CX Admin Console
2. Hardware Phones → Phone Templates
3. AX83H-Template wählen
4. Remote Phonebook URL eintragen
5. Alle Telefone laden Update automatisch

---

## 📊 Überwachung

### Live-Logs anschauen

```bash
# Systemd-Logs (Real-time)
sudo journalctl -u 3cx-yealink-sync.service -f

# Oder Datei-Log
tail -f /var/log/3cx_yealink_sync.log
```

### Status prüfen

```bash
# Service-Status
sudo systemctl status 3cx-yealink-sync.service

# HTTP-API
curl http://localhost:8080/status | jq
```

### Kontakte zählen

```bash
# CSV
tail -n +2 /var/www/html/phonebook/phonebook.csv | wc -l

# XML
grep -c "<contact>" /var/www/html/phonebook/phonebook.xml
```

---

## 🧪 Testen

### Schnell-Test

```bash
# Im Skript-Verzeichnis
chmod +x test_3cx_yealink_sync.sh
./test_3cx_yealink_sync.sh
```

Prüft automatisch:
- Python-Installation
- Skript-Dateien
- CSV-Datei & Header
- Service-Status
- Port 8080
- Ausgabe-Dateien
- Logs

### Manueller Test

```bash
# Einmalige Synchronisation (keine Daemon)
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --once

# Logs ansehen
ls -la /var/www/html/phonebook/
file /var/www/html/phonebook/phonebook.csv
```

---

## 🐛 Troubleshooting

### Problem: "CSV nicht gefunden"

```bash
# Prüfe, ob 3CX-Export funktioniert
ls -la /var/lib/3cx/phonebook/

# Falls nicht: Manuell in 3CX exportieren
# (3CX Admin Console → Phonebook → Export as CSV)
```

### Problem: "Keine Kontakte geladen"

```bash
# CSV-Header prüfen
head -n1 /var/lib/3cx/phonebook/contacts_3cx.csv

# Sollte enthalten: FirstName,LastName,Company,Mobile,Business,...
```

### Problem: Service stoppt immer

```bash
# Im Foreground debuggen
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --log-file /tmp/debug.log

# Logs ansehen
tail -f /tmp/debug.log
```

**Mehr Lösungen:** Siehe [INSTALLATIONSANLEITUNG.md#troubleshooting](INSTALLATIONSANLEITUNG.md#troubleshooting)

---

## ⚙️ Konfiguration

### Sync-Intervall ändern

```bash
# In systemd-Service oder command-line:
--interval 60       # Jede Minute
--interval 300      # Alle 5 Minuten (Standard)
--interval 1800     # Alle 30 Minuten
```

### Port ändern

```bash
--port 8080         # Standard
--port 9090         # Custom
```

### Logs erweitern

```bash
--log-file /var/log/3cx_yealink_sync.log
```

---

## 📞 Feldmapping

Die **4 Nummernfelder** der Yealink werden intelligent aus 3CX gefüllt:

| Yealink-Feld | Quelle (primär) | Fallback |
|---|---|---|
| **office_number** | Business | Business2 |
| **mobile_number** | Mobile | (leer) |
| **other_number** | Mobile2 | Home |
| **businessFax** | BusinessFax | Other |

**Beispiel:**
- Kontakt hat `Business=0231555` & `Business2=0231666`
  → Yealink zeigt `office_number=0231555` (primär)

- Kontakt hat nur `BusinessFax=0231777` (kein `Other`)
  → Yealink zeigt `businessFax=0231777`

---

## 🔒 Sicherheit

### Service läuft als unprivilegierter Benutzer
```bash
User=3cx_sync
Group=3cx_sync
```

### Logs landen in Systemd (Journald)
```bash
journalctl -u 3cx-yealink-sync.service
```

### CSV-Datei sollte geschützt sein
```bash
# Auf 3CX-Server
chmod 640 /var/lib/3cx/phonebook/contacts_3cx.csv
chown 3cx_sync:3cx_sync /var/lib/3cx/phonebook/contacts_3cx.csv
```

---

## 📚 Dokumentation

| Datei | Inhalt |
|-------|--------|
| [QUICK_START.md](QUICK_START.md) | 10-Minuten-Setup |
| [INSTALLATIONSANLEITUNG.md](INSTALLATIONSANLEITUNG.md) | Detaillierte Anleitung (200+ Zeilen) |
| [3cx_yealink_sync.py](3cx_yealink_sync.py) | Quellcode (gut kommentiert) |

---

## ❓ FAQ

**F: Funktioniert es auch mit anderen Telefonen (Snom, Gigaset, etc.)?**  
A: Das CSV-Format ist Standard – sollte mit den meisten VoIP-Telefonen funktionieren. XML ist Yealink-spezifisch.

**F: Was passiert, wenn 3CX-CSV nicht aktualisiert wird?**  
A: Das Skript lädt regelmäßig (alle 5 Min), zeigt aber immer den letzten erfolgreich geladenen Stand. Falls CSV fehlt, zeigt es eine Warnung im Log.

**F: Kann ich mehrere 3CX-Systeme synchronisieren?**  
A: Ja – starten Sie mehrere Service-Instanzen mit verschiedenen CSV-Quellen auf verschiedenen Ports.

**F: Auf welchem Port läuft der HTTP-Server?**  
A: Standard ist **8080** (konfigurierbar mit `--port`).

**F: Kann ich die Dateiformate (CSV/XML) anpassen?**  
A: Ja – bearbeite die Funktionen `write_yealink_csv()` und `write_yealink_xml()` im Skript.

---

## 🤝 Support

Für Probleme:
1. Lies [INSTALLATIONSANLEITUNG.md#troubleshooting](INSTALLATIONSANLEITUNG.md#troubleshooting)
2. Führe `test_3cx_yealink_sync.sh` aus
3. Prüfe Logs: `journalctl -u 3cx-yealink-sync.service -n 100`
4. Kontaktiere deinen Admin oder schau in die 3CX-Community

---

## 📋 Lizenz & Haftung

Dieses Skript wird AS-IS bereitgestellt. Teste es in einer Test-Umgebung, bevor du es produktiv einsetzt.

---

## ✅ Checkliste vor dem Produktiveinsatz

- [ ] Alle Dateien kopiert (`3cx_yealink_sync.py`, Service-Datei, etc.)
- [ ] Python 3.7+ installiert
- [ ] 3CX-CSV regelmäßig exportiert & verfügbar
- [ ] Test mit `--once` erfolgreich
- [ ] Systemd-Service installiert & läuft
- [ ] HTTP-Server antwortet auf Port 8080
- [ ] Telefone konfiguriert (Remote Phonebook URL)
- [ ] Kontakte auf Telefon sichtbar (alle 4 Felder)
- [ ] Logs überwacht (kein Error/Warning)
- [ ] Dokumentation gelesen

---

**Version:** 1.0  
**Datum:** 2026-08-19  
**Für:** Yealink AX83H/AX86R + 3CX auf Linux

---

Fragen? → Siehe INSTALLATIONSANLEITUNG.md oder QUICK_START.md 🚀
