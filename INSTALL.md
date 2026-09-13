# Installation Guide

## 🚀 Schnelle Installation (von GitHub)

### Schritt 1: Repository klonen

```bash
cd /tmp
git clone https://github.com/piohabi/3cx_custom_phonebook.git
cd 3cx_custom_phonebook
```

### Schritt 2: Abhängigkeiten installieren

```bash
# Grundsystem
sudo apt-get update
sudo apt-get install -y python3 python3-pip

# Python-Pakete
pip install cryptography requests
```

### Schritt 3: Skript installieren

```bash
# Verzeichnis erstellen
sudo mkdir -p /opt/3cx_yealink_sync
sudo chown $(whoami):$(whoami) /opt/3cx_yealink_sync

# Skript kopieren
cp 3cx_yealink_sync_pro.py /opt/3cx_yealink_sync/
chmod +x /opt/3cx_yealink_sync/3cx_yealink_sync_pro.py
```

### Schritt 4: Setup starten

```bash
cd /opt/3cx_yealink_sync
python3 3cx_yealink_sync_pro.py --setup --port 8080
```

### Schritt 5: Browser öffnen

```
http://localhost:8080
```

**Formular ausfüllen:**
- **FQDN:** 3cx.example.com
- **Extension:** 101 (oder Ihre Admin-Extension)
- **Passwort:** Ihr Passwort

Klicken Sie **"Verbindung testen"** → ✓ → **"Speichern & Starten"**

---

## 🔧 Systemd-Service (Produktiv)

### Service installieren

```bash
sudo cp systemd-services/3cx-yealink-sync-pro.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable 3cx-yealink-sync-pro.service
sudo systemctl start 3cx-yealink-sync-pro.service
```

### Service überwachen

```bash
# Status
sudo systemctl status 3cx-yealink-sync-pro.service

# Logs live
sudo journalctl -u 3cx-yealink-sync-pro.service -f

# Letzte 50 Zeilen
sudo journalctl -u 3cx-yealink-sync-pro.service -n 50
```

---

## 📱 Telefone konfigurieren

### Yealink AX83H/AX86R

1. Admin-Interface: `http://<TELEFON_IP>`
2. **Directory** → **Local Phonebook**
3. **Remote Phonebook URL:** `http://<SERVER_IP>:8080/phonebook.csv`
4. **Refresh Interval:** `3600`
5. **Save** → **Reboot**

---

## ✅ Test

```bash
# Test-Skript ausführen
chmod +x test_3cx_yealink_sync.sh
./test_3cx_yealink_sync.sh

# Manueller Test
curl http://localhost:8080/status
```

---

## 🆚 STANDARD-Version (Alternative)

Wenn Sie die CSV-basierte Version bevorzugen:

```bash
cp 3cx_yealink_sync.py /opt/3cx_yealink_sync/

python3 3cx_yealink_sync.py \
  --input /var/lib/3cx/phonebook/contacts_3cx.csv \
  --output /var/www/html/phonebook \
  --daemon
```

Siehe auch: `docs/QUICK_START.md`

---

## 🐛 Troubleshooting

### "Fehler: config.json nicht gefunden"

```bash
# Führe Setup erneut aus
python3 3cx_yealink_sync_pro.py --setup
```

### "Port 8080 schon in Benutzung"

```bash
# Anderer Port
python3 3cx_yealink_sync_pro.py --setup --port 9090
```

### "ModuleNotFoundError: No module named 'cryptography'"

```bash
pip install --upgrade cryptography requests
```

### "ConnectionError: 3CX nicht erreichbar"

```bash
# Testen
ping 3cx.example.com
curl -k https://3cx.example.com/api/v1/ping
```

---

## 📚 Weitere Dokumentation

- [README.md](README.md) – Übersicht
- [docs/README_PRO.md](docs/README_PRO.md) – Features
- [docs/PRO_QUICKSTART.md](docs/PRO_QUICKSTART.md) – Schnelleinstieg
- [docs/INSTALLATIONSANLEITUNG.md](docs/INSTALLATIONSANLEITUNG.md) – Detailliert

---

Viel Erfolg! 🚀
