# 3CX Custom Phonebook Server

Produktiv getesteter Kontaktbuch-Server für 3CX v20 und Yealink AX83H/AX86R. Der Dienst meldet sich über den 3CX WebClient-Endpunkt an, lädt Kontakte aus der XAPI und veröffentlicht sie als `YealinkIPPhoneBook`-XML.

## Funktionen

- 3CX-v20-Anmeldung und XAPI-Paginierung
- Yealink XML mit `Name` sowie `Phone1` bis `Phone4`
- Webportal für Konfiguration und Betriebsstatus
- Verbindungstest und sofortige Synchronisierung
- Dynamischer Provisionierungslink mit Kopierfunktion
- Kontaktliste mit Suche und Seitennavigation
- Getrennte Rohdaten- und Yealink-Vorschau
- Einstellbare Feldpriorität und optionales Normalisieren von Rufnummern
- Optionale Duplikatfilterung
- Zusätzliche Telefonbuchgruppen nach 3CX-Feldern wie `Tag` oder `Department`
- IP-Allowlist und Zugriffstoken
- Systemd-Service mit eigenem Benutzer
- Automatische Sicherung der Konfiguration vor Änderungen

## Voraussetzungen

- Debian 12 oder vergleichbares Linux mit systemd
- Python 3.11+ und `python3-venv`
- Ausgehender HTTPS-Zugriff zur 3CX-Anlage
- Ein 3CX-Benutzer mit Leserechten für Kontakte
- Eingehender TCP-Port 8095 nur von den benötigten Standorten

## Installation

```bash
git clone https://github.com/piohabi/3cx_custom_phonebook.git
cd 3cx_custom_phonebook
sudo apt-get update
sudo apt-get install -y python3 python3-venv
sudo ./install.sh
```

Danach `http://SERVER:8095` öffnen. Beim ersten Start müssen 3CX-URL, Benutzername und Passwort eingetragen werden. `install.sh` erzeugt automatisch einen zufälligen Zugriffstoken.

## Konfiguration

Die produktive Konfiguration liegt außerhalb des Repositorys:

```text
/opt/prooffice-phonebook/config.yml
/opt/prooffice-phonebook/.env
```

Als Vorlage dient [`config.example.yml`](config.example.yml). Zugangsdaten und Zugriffstoken gehören ausschließlich in `.env` und werden durch `.gitignore` ausgeschlossen.

Im Portal lassen sich Seitentitel, Synchronisationsintervall, Yealink-Gruppenname, Feldpriorität, Rufnummernnormalisierung, Duplikatfilterung und zusätzliche Telefonbuchgruppen konfigurieren. Gruppen verwenden das Format `Name|3CX-Feld|Suchwert`.

## Provisionierung

Das Portal erzeugt den vollständigen Link automatisch:

```text
http://SERVER:8095/phonebook.xml?key=ZUGRIFFSTOKEN
```

Zusätzliche Telefonbuchgruppen erhalten eigene Links. AX83H und AX86R verwenden dasselbe `YealinkIPPhoneBook`-Schema.

## Betrieb und Updates

```bash
sudo systemctl status prooffice-phonebook
sudo journalctl -u prooffice-phonebook -f
curl http://127.0.0.1:8095/status.json
```

Ein Update überschreibt weder `config.yml` noch `.env`:

```bash
cd /pfad/zu/3cx_custom_phonebook
git pull --ff-only
sudo ./install.sh
```

Die Quellversion im Repository ist die maßgebliche Version. Änderungen werden zuerst hier committed und danach mit `sudo ./install.sh` ausgerollt. Kundenspezifische Konfiguration, Passwörter, Tokens, erzeugte Telefonbücher und Logs werden nicht committed.

Vor einem Release:

```bash
python3 -m py_compile app.py
shellcheck install.sh
```

## Bestehende ältere Versionen

`3cx_yealink_sync.py` und `3cx_yealink_sync_pro.py` stammen aus der früheren CSV/REST-Implementierung. Für neue Installationen ist ausschließlich `app.py` mit `prooffice-phonebook.service` vorgesehen.

## Sicherheit

Portal und Telefonbuch dürfen nur für ausdrücklich freigegebene Quell-IP-Adressen erreichbar sein. Das Portal verwendet derzeit HTTP; Zugangsdaten sollten über einen privaten Netzwerkpfad oder SSH-Tunnel eingegeben werden, bis die geplante HTTPS-/VPN-Trennung umgesetzt ist.

## Lizenz

MIT – siehe [`LICENSE`](LICENSE).
