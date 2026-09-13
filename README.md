# 3CX ↔ Yealink AX Phonebook Sync

> **Automatische Kontakt-Synchronisation zwischen 3CX Telefonanlage und Yealink AX83H/AX86R Telefonen**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/downloads/)

---

## 🎯 Übersicht

Dieses System synchronisiert Kontakte automatisch aus Ihrer **3CX-Telefonanlage** zu den **Yealink AX83H/AX86R Telefonen** (oder kompatible Modelle).

### Besonderheiten:

✅ **Automatische Synchronisation** – Alle 5 Minuten (konfigurierbar)  
✅ **Zwei Versionen** – STANDARD (CSV) oder PRO (Web-Setup + REST API)  
✅ **Alle 4 Nummernfelder** – Office, Mobile, Other, Fax  
✅ **Einfache Installation** – Quick-Start in 5-15 Minuten  
✅ **Produktionsreif** – Mit Error-Handling und Logging  
✅ **Open Source** – MIT-Lizenz

---

## 🚀 Quick Start

### OPTION A: PRO-Version (Empfohlen für Anfänger)

```bash
# 1. Repository klonen
git clone https://github.com/piohabi/3cx_custom_phonebook.git
cd 3cx_custom_phonebook

# 2. Installation
sudo cp 3cx_yealink_sync_pro.py /opt/3cx_yealink_sync/
cd /opt/3cx_yealink_sync
python3 3cx_yealink_sync_pro.py --setup

# 3. Browser öffnen
# http://localhost:8080
# Formular ausfüllen (FQDN, Extension, Passwort)
# Speichern & fertig!
```

**Zeitaufwand:** 5-10 Minuten  
**Dokumetation:** Siehe `docs/PRO_QUICKSTART.md`

---

### OPTION B: STANDARD-Version (CSV-basiert)

```bash
# 1. Repository klonen
git clone https://github.com/piohabi/3cx_custom_phonebook.git
cd 3cx_custom_phonebook

# 2. Installation
sudo cp 3cx_yealink_sync.py /opt/3cx_yealink_sync/
python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --daemon

# 3. Systemd-Service installieren
sudo cp systemd-services/3cx-yealink-sync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now 3cx-yealink-sync.service
```

**Zeitaufwand:** 10-15 Minuten  
**Dokumentation:** Siehe `docs/QUICK_START.md`

---

## 📋 Anforderungen

### System:
- **Linux** (Debian 11+, Ubuntu 20.04+, CentOS 8+)
- **Python 3.7+**
- **pip** für Abhängigkeiten

### 3CX:
- **3CX v16+** mit REST API (Standard)
- **Admin-Extension** oder Systemeigentümer-Zugang

### Yealink:
- **AX83H** oder **AX86R** (oder kompatible Modelle)
- Netzwerk-Erreichbarkeit zum Sync-Server

---

## 📦 Repository-Struktur

```
3cx_custom_phonebook/
├── README.md                           ← Sie sind hier
├── .gitignore
├── LICENSE
│
├── 3cx_yealink_sync.py                 ← STANDARD Version (CSV)
├── 3cx_yealink_sync_pro.py             ← PRO Version (Web + API)
├── test_3cx_yealink_sync.sh            ← Test-Skript
│
├── docs/
│   ├── README_STANDARD.md              ← Feature-Übersicht STANDARD
│   ├── README_PRO.md                   ← Feature-Übersicht PRO
│   ├── QUICK_START.md                  ← Schnelleinstieg STANDARD
│   ├── PRO_QUICKSTART.md               ← Schnelleinstieg PRO
│   ├── INSTALLATIONSANLEITUNG.md       ← Detaillierte Anleitung
│   └── ...
│
├── systemd-services/
│   ├── 3cx-yealink-sync.service        ← Service STANDARD
│   └── 3cx-yealink-sync-pro.service    ← Service PRO
│
└── examples/
    └── (Konfigurationsbeispiele)
```

---

## 🎯 Welche Version?

| Aspekt | STANDARD | PRO |
|--------|----------|-----|
| **Datenquelle** | 3CX CSV-Export | 3CX REST API |
| **Konfiguration** | Kommandozeile | Web-Browser |
| **Setup-Zeit** | 15 Min | 5 Min |
| **Anfänger-freundlich** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Für wen?** | Tech-Admins | Alle |

→ **Empfehlung:** Starten Sie mit **PRO-Version** für einfache Installation!

---

## 📚 Dokumentation

### Schnelleinstieg:
- **[PRO_QUICKSTART.md](docs/PRO_QUICKSTART.md)** – 5-Minuten-Setup (PRO)
- **[QUICK_START.md](docs/QUICK_START.md)** – 10-Minuten-Setup (STANDARD)

### Detailliert:
- **[README_PRO.md](docs/README_PRO.md)** – Features & Vergleich
- **[INSTALLATIONSANLEITUNG.md](docs/INSTALLATIONSANLEITUNG.md)** – Ausführliche Docs

### Support:
- **[test_3cx_yealink_sync.sh](test_3cx_yealink_sync.sh)** – Diagnose-Skript

---

## 🔧 Installation vom Server aus

### Methode 1: Git Clone (empfohlen)

```bash
# Auf Linux-Server als root
cd /tmp
git clone https://github.com/piohabi/3cx_custom_phonebook.git
cd 3cx_custom_phonebook

# PRO-Version installieren
sudo mkdir -p /opt/3cx_yealink_sync
sudo cp 3cx_yealink_sync_pro.py /opt/3cx_yealink_sync/
sudo chmod +x /opt/3cx_yealink_sync/3cx_yealink_sync_pro.py

# Starten
cd /opt/3cx_yealink_sync
python3 3cx_yealink_sync_pro.py --setup --port 8080

# Browser: http://localhost:8080
```

### Methode 2: Einzelne Skripte herunterladen

```bash
# Nur das Haupt-Skript
curl -O https://raw.githubusercontent.com/piohabi/3cx_custom_phonebook/master/3cx_yealink_sync_pro.py
chmod +x 3cx_yealink_sync_pro.py
python3 3cx_yealink_sync_pro.py --setup
```

---

## 🎛️ Konfiguration

### PRO-Version: Web-Interface

```
Browser öffnen: http://localhost:8080
├─ FQDN eingeben (z.B. 3cx.example.com)
├─ Extension eingeben (z.B. 101)
├─ Passwort eingeben
├─ "Verbindung testen" klicken
└─ "Speichern & Starten" klicken
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

## 📱 Telefone konfigurieren

### Auf Yealink AX83H/AX86R:

1. Admin-Interface öffnen: `http://<TELEFON_IP>`
2. **Directory** → **Local Phonebook**
3. **Remote Phonebook URL:**
   ```
   http://<SERVER_IP>:8080/phonebook.csv
   ```
4. **Refresh Interval:** `3600` (1 Stunde)
5. **Save** → **Reboot**

### Über 3CX-Provisioning (automatisch):

```
3CX Admin Console
  → Hardware Phones
    → Phone Templates
      → AX83H
        → Remote Phonebook URL: http://<SERVER_IP>:8080/phonebook.csv
        → Save
```

---

## 🧪 Testen

### Test-Skript ausführen

```bash
chmod +x test_3cx_yealink_sync.sh
./test_3cx_yealink_sync.sh
```

Prüft automatisch:
- ✓ Python-Installation
- ✓ Dateien & Berechtigungen
- ✓ Service-Status
- ✓ HTTP-Server
- ✓ Ausgabedateien

---

## 🐛 Troubleshooting

### "Verbindung fehlgeschlagen"

```bash
# 3CX erreichbar?
ping 3cx.example.com

# REST API funktioniert?
curl -k https://3cx.example.com/api/v1/ping

# Logs prüfen
sudo journalctl -u 3cx-yealink-sync-pro.service -n 50
```

### "Telefone zeigen keine Kontakte"

```bash
# HTTP-Server läuft?
curl http://localhost:8080/phonebook.csv

# Kontakte vorhanden?
wc -l /var/www/html/phonebook/phonebook.csv

# Service läuft?
sudo systemctl status 3cx-yealink-sync-pro.service
```

Weitere Lösungen: Siehe `docs/INSTALLATIONSANLEITUNG.md`

---

## 📊 Feldmapping

Die **4 Yealink-Nummernfelder** werden intelligent aus 3CX gefüllt:

| Yealink-Feld | 3CX-Quelle (primär) | Fallback |
|---|---|---|
| **Office** | Business | Business2 |
| **Mobile** | Mobile | – |
| **Other** | Mobile2 | Home |
| **Fax** | BusinessFax | Other |

---

## 🔐 Sicherheit

✅ **Passwort-Verschlüsselung** – AES (Fernet, PRO-Version)  
✅ **HTTPS zu 3CX** – Sichere REST API-Verbindung  
✅ **Benutzer-Isolation** – Service läuft als `3cx_sync` (kein root)  
✅ **Self-Signed Certs OK** – Funktioniert mit 3CX-Standardzertifikaten

---

## 📄 Lizenz

MIT License – Siehe [LICENSE](LICENSE)

---

## 🤝 Beiträge

Fehler gefunden? Feature-Request?

→ [Issues erstellen](https://github.com/piohabi/3cx_custom_phonebook/issues)

---

## 📞 Support

### Ressourcen:
- 📖 [Dokumentation](docs/)
- 🐛 [Issues & Bugs](https://github.com/piohabi/3cx_custom_phonebook/issues)
- 💬 [Diskussionen](https://github.com/piohabi/3cx_custom_phonebook/discussions)

### Schnelle Hilfe:
```bash
python3 3cx_yealink_sync.py --help
python3 3cx_yealink_sync_pro.py --help
```

---

## 🎉 Danke!

Viel Erfolg bei der Einrichtung! 🚀

---

**Version:** 2.0  
**Zuletzt aktualisiert:** 2026-09-13  
**Für:** 3CX + Yealink AX83H/AX86R auf Linux
