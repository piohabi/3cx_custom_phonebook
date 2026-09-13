# 🚀 Push zu GitHub

Das Repository ist lokal vorbereitet. Führen Sie diese Befehle aus, um es auf GitHub zu pushen:

## Option 1: HTTPS (einfach)

```bash
cd /pfad/zu/3cx_custom_phonebook

git remote add origin https://github.com/piohabi/3cx_custom_phonebook.git
git branch -M main
git push -u origin main
```

**Dann:** Sie werden aufgefordert, GitHub-Credentials einzugeben (Personal Access Token oder GitHub-Passwort) — mit installiertem Git Credential Manager öffnet sich stattdessen ein Browser-Login.

---

## Option 2: SSH (schneller, wenn SSH-Key konfiguriert)

```bash
cd /pfad/zu/3cx_custom_phonebook

git remote add origin git@github.com:piohabi/3cx_custom_phonebook.git
git branch -M main
git push -u origin main
```

---

## ✅ Fertig!

Nach dem Push können Sie direkt vom Server installieren:

```bash
# Auf Ihrem Linux-Server
cd /tmp
git clone https://github.com/piohabi/3cx_custom_phonebook.git
cd 3cx_custom_phonebook

# PRO-Version starten
cp 3cx_yealink_sync_pro.py /opt/3cx_yealink_sync/
python3 /opt/3cx_yealink_sync/3cx_yealink_sync_pro.py --setup
```

Browser öffnen: **http://localhost:8080** → Setup durchführen ✓

---

## 🐛 Wenn etwas schiefgeht

### "remote already exists"

```bash
git remote remove origin
# Dann erneut versuchen
```

### "fatal: No commits yet"

Das Repository ist noch leer. Stellen Sie sicher, dass Sie diesen Befehl im richtigen Verzeichnis ausführen:

```bash
cd /pfad/zu/3cx_custom_phonebook
ls -la .git
```

### Authentication failed

Wenn Sie HTTPS verwenden:
- Verwenden Sie statt Passwort einen **Personal Access Token**
- [GitHub → Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
- Token muss `repo` Rechte haben

Oder verwenden Sie SSH:
```bash
git remote set-url origin git@github.com:piohabi/3cx_custom_phonebook.git
```

---

Viel Erfolg! 🎉
