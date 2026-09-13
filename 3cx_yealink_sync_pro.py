#!/usr/bin/env python3
"""
3CX → Yealink AX Series Phonebook Sync Service (PRO Version)

Mit integriertem Web-Setup-Interface und direkter 3CX REST API Integration

Features:
- Web-Interface für Konfiguration (http://localhost:8080/setup)
- Direkte 3CX REST API Integration (keine CSV nötig)
- Sichere Speicherung von Credentials (verschlüsselt)
- Automatische Kontakt-Synchronisation
- Status-Dashboard & Monitoring API
"""

import os
import sys
import json
import csv
import logging
import time
import argparse
import requests
import threading
import signal
import base64
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urljoin
from typing import Dict, List, Optional

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("⚠️  cryptography nicht installiert. Install: pip install cryptography")
    sys.exit(1)


# ============================================================================
# KONFIGURATION
# ============================================================================

DEFAULT_INTERVAL = 300  # 5 Minuten
DEFAULT_PORT = 8080
CONFIG_FILE = "/opt/3cx_yealink_sync/config.json"
LOG_FILE = "/var/log/3cx_yealink_sync.log"
OUTPUT_DIR = "/var/www/html/phonebook"


# ============================================================================
# LOGGING
# ============================================================================

def setup_logging(log_file=None):
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"⚠️  Log-Datei konnte nicht erstellt werden: {e}")

    return logger


logger = setup_logging(LOG_FILE)


# ============================================================================
# KONFIGURATION MANAGEMENT
# ============================================================================

class ConfigManager:
    """Verwaltet Konfiguration mit Verschlüsselung für Passwords"""

    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = config_file
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
        self.config = self._load_config()

    def _get_or_create_key(self):
        """Erstellt oder lädt den Verschlüsselungs-Key"""
        key_file = os.path.join(os.path.dirname(self.config_file), ".fernet_key")

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)
            return key

    def _load_config(self) -> dict:
        """Lädt Konfiguration aus Datei"""
        if not os.path.exists(self.config_file):
            return {
                "mode": "api",  # "api" oder "csv"
                "3cx_fqdn": "",
                "3cx_extension": "",
                "3cx_password": "",  # Verschlüsselt
                "sync_interval": DEFAULT_INTERVAL,
                "http_port": DEFAULT_PORT,
                "output_dir": OUTPUT_DIR,
                "last_sync": None,
                "contact_count": 0,
                "csv_path": "/var/lib/3cx/phonebook/contacts_3cx.csv"
            }

        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfiguration: {e}")
            return {}

    def save_config(self, config: dict) -> bool:
        """Speichert Konfiguration"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            os.chmod(self.config_file, 0o600)
            logger.info(f"✓ Konfiguration gespeichert: {self.config_file}")
            self.config = config
            return True
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Konfiguration: {e}")
            return False

    def encrypt_password(self, password: str) -> str:
        """Verschlüsselt Password"""
        return self.cipher.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted: str) -> str:
        """Entschlüsselt Password"""
        try:
            return self.cipher.decrypt(encrypted.encode()).decode()
        except Exception:
            return ""

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value


# ============================================================================
# 3CX REST API CLIENT
# ============================================================================

class ThreeCXAPIClient:
    """Kommuniziert mit 3CX REST API"""

    def __init__(self, fqdn: str, extension: str, password: str):
        self.fqdn = fqdn
        self.extension = extension
        self.password = password
        self.base_url = f"https://{fqdn}/api/v1"
        self.token = None
        self.session = requests.Session()
        self.session.verify = False  # SSL-Warnung ignorieren (für Self-Signed Certs)
        requests.packages.urllib3.disable_warnings()

    def login(self) -> bool:
        """Authentifiziert bei 3CX"""
        try:
            login_url = f"{self.base_url}/Accounts/Login"
            payload = {
                "username": self.extension,
                "password": self.password
            }

            response = self.session.post(login_url, json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                self.token = data.get('sessionID')
                logger.info(f"✓ 3CX Login erfolgreich (Extension: {self.extension})")
                return True
            else:
                logger.error(f"3CX Login fehlgeschlagen: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Fehler beim 3CX Login: {e}")
            return False

    def get_phonebook_contacts(self) -> List[dict]:
        """Holt alle Firmen-Kontakte aus 3CX Phonebook"""
        if not self.token:
            if not self.login():
                return []

        try:
            # 3CX Phonebook API Endpoint
            contacts_url = f"{self.base_url}/Phonebook"
            headers = {
                'Cookie': f'sessionID={self.token}'
            }

            response = self.session.get(contacts_url, headers=headers, timeout=30)

            if response.status_code == 200:
                contacts_data = response.json()
                logger.info(f"✓ {len(contacts_data)} Kontakte von 3CX abgerufen")
                return contacts_data
            else:
                logger.error(f"Fehler beim Abrufen der Kontakte: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Kontakte: {e}")
            return []

    def test_connection(self) -> tuple[bool, str]:
        """Testet die Verbindung zur 3CX"""
        try:
            if self.login():
                return True, "✓ Verbindung zu 3CX erfolgreich!"
            else:
                return False, "✗ Login fehlgeschlagen - prüfen Sie FQDN, Extension und Passwort"
        except Exception as e:
            return False, f"✗ Fehler: {str(e)}"


# ============================================================================
# KONTAKT-KONVERTIERUNG
# ============================================================================

def convert_3cx_contacts_to_yealink(contacts: List[dict]) -> List[dict]:
    """
    Konvertiert 3CX-Kontakte in Yealink AX Format
    """
    yealink_contacts = []

    for contact in contacts:
        try:
            # 3CX Datenstruktur
            name = contact.get('name', '') or contact.get('Name', '')
            company = contact.get('company', '') or contact.get('Company', '')
            email = contact.get('email', '') or contact.get('Email', '')

            display_name = company if company else name
            if not display_name:
                continue

            # Nummernfelder extrahieren
            numbers = contact.get('numbers', []) if isinstance(contact.get('numbers'), list) else []

            office_number = ""
            mobile_number = ""
            other_number = ""
            business_fax = ""

            # Intelligentes Mapping der Nummerntypen
            for num_entry in numbers:
                if isinstance(num_entry, dict):
                    phone_type = num_entry.get('type', '').lower()
                    phone_number = num_entry.get('number', '').strip()

                    if phone_type in ['business', 'work', 'office']:
                        if not office_number:
                            office_number = phone_number
                    elif phone_type in ['mobile', 'cell', 'cellular']:
                        if not mobile_number:
                            mobile_number = phone_number
                    elif phone_type in ['home']:
                        if not other_number:
                            other_number = phone_number
                    elif phone_type in ['fax', 'businessfax']:
                        if not business_fax:
                            business_fax = phone_number
                    elif phone_type in ['other', 'additional']:
                        if not other_number:
                            other_number = phone_number

            # Fallback für fehlende Felder (aus flachen Feldern)
            if not office_number:
                office_number = contact.get('officeNumber', '') or contact.get('business', '')
            if not mobile_number:
                mobile_number = contact.get('mobileNumber', '') or contact.get('mobile', '')
            if not other_number:
                other_number = contact.get('otherNumber', '') or contact.get('home', '')
            if not business_fax:
                business_fax = contact.get('businessFax', '') or contact.get('fax', '')

            # Nur wenn mindestens eine Nummer
            if any([office_number, mobile_number, other_number, business_fax]):
                yealink_contact = {
                    'display_name': display_name,
                    'company': company,
                    'email': email,
                    'office_number': office_number,
                    'mobile_number': mobile_number,
                    'other_number': other_number,
                    'businessFax': business_fax,
                }
                yealink_contacts.append(yealink_contact)

        except Exception as e:
            logger.warning(f"Fehler bei Kontakt-Konvertierung: {e}")
            continue

    return yealink_contacts


# ============================================================================
# EXPORT FUNKTIONEN
# ============================================================================

def write_yealink_csv(contacts: List[dict], output_path: str) -> bool:
    """Schreibt Kontakte als CSV"""
    try:
        fieldnames = [
            'display_name', 'office_number', 'mobile_number', 'other_number',
            'businessFax', 'line', 'ring', 'auto_divert', 'priority',
            'group_id_name', 'default_photo', 'photo_data'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_NONNUMERIC)
            writer.writeheader()

            for contact in contacts:
                row = {
                    'display_name': contact['display_name'],
                    'office_number': contact['office_number'],
                    'mobile_number': contact['mobile_number'],
                    'other_number': contact['other_number'],
                    'businessFax': contact['businessFax'],
                    'line': -1,
                    'ring': 'Auto',
                    'auto_divert': '',
                    'priority': '',
                    'group_id_name': 'All Contacts',
                    'default_photo': 'Default:default_contact_image.png',
                    'photo_data': ''
                }
                writer.writerow(row)

        logger.info(f"✓ CSV geschrieben: {output_path} ({len(contacts)} Kontakte)")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Schreiben der CSV: {e}")
        return False


def write_yealink_xml(contacts: List[dict], output_path: str) -> bool:
    """Schreibt Kontakte als XML"""
    try:
        xml_lines = [
            '<?xml version="1.0"?>',
            '<vp_contact>',
            '  <root_group>',
            '    <group display_name="All Contacts"/>',
            '    <group display_name="Blocklist"/>',
            '  </root_group>',
            '  <root_contact>'
        ]

        for contact in contacts:
            xml_lines.append('    <contact>')
            xml_lines.append(f'      <display_name>{escape_xml(contact["display_name"])}</display_name>')

            if contact['company']:
                xml_lines.append(f'      <company>{escape_xml(contact["company"])}</company>')

            if contact['email']:
                xml_lines.append(f'      <email>{escape_xml(contact["email"])}</email>')

            # Phone-Einträge
            if contact['office_number']:
                xml_lines.append('      <phone>')
                xml_lines.append(f'        <phone_number>{escape_xml(contact["office_number"])}</phone_number>')
                xml_lines.append('        <label>Office</label>')
                xml_lines.append('      </phone>')

            if contact['mobile_number']:
                xml_lines.append('      <phone>')
                xml_lines.append(f'        <phone_number>{escape_xml(contact["mobile_number"])}</phone_number>')
                xml_lines.append('        <label>Mobile</label>')
                xml_lines.append('      </phone>')

            if contact['other_number']:
                xml_lines.append('      <phone>')
                xml_lines.append(f'        <phone_number>{escape_xml(contact["other_number"])}</phone_number>')
                xml_lines.append('        <label>Other</label>')
                xml_lines.append('      </phone>')

            if contact['businessFax']:
                xml_lines.append('      <phone>')
                xml_lines.append(f'        <phone_number>{escape_xml(contact["businessFax"])}</phone_number>')
                xml_lines.append('        <label>Fax</label>')
                xml_lines.append('      </phone>')

            xml_lines.append('    </contact>')

        xml_lines.extend(['  </root_contact>', '</vp_contact>'])

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_lines))

        logger.info(f"✓ XML geschrieben: {output_path} ({len(contacts)} Kontakte)")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Schreiben der XML: {e}")
        return False


def escape_xml(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;'))


# ============================================================================
# SYNCHRONISATION
# ============================================================================

class PhonebookSyncer:
    """Synchronisiert Phonebook regelmäßig"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.stop_event = threading.Event()
        self.http_server = None
        self.last_sync = None
        self.contact_count = 0

    def sync_from_api(self) -> bool:
        """Synchronisiert von 3CX API"""
        try:
            client = ThreeCXAPIClient(
                fqdn=self.config.get('3cx_fqdn'),
                extension=self.config.get('3cx_extension'),
                password=self.config.decrypt_password(self.config.get('3cx_password', ''))
            )

            contacts_raw = client.get_phonebook_contacts()
            if not contacts_raw:
                logger.warning("Keine Kontakte von 3CX abgerufen")
                return False

            contacts = convert_3cx_contacts_to_yealink(contacts_raw)
            self.contact_count = len(contacts)

            output_dir = self.config.get('output_dir', OUTPUT_DIR)
            os.makedirs(output_dir, exist_ok=True)

            write_yealink_csv(contacts, os.path.join(output_dir, 'phonebook.csv'))
            write_yealink_xml(contacts, os.path.join(output_dir, 'phonebook.xml'))

            self.last_sync = datetime.now().isoformat()
            self.config.set('last_sync', self.last_sync)
            self.config.set('contact_count', self.contact_count)
            self.config.save_config(self.config.config)

            return True

        except Exception as e:
            logger.error(f"Fehler bei API-Synchronisation: {e}")
            return False

    def sync(self) -> bool:
        """Führt Synchronisation durch"""
        logger.info("─" * 60)
        logger.info(f"Sync-Lauf: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        mode = self.config.get('mode', 'api')

        if mode == 'api':
            success = self.sync_from_api()
        else:
            logger.info("CSV-Modus nicht implementiert in dieser Version")
            success = False

        if success:
            logger.info(f"✓ Sync erfolgreich: {self.contact_count} Kontakte")
        else:
            logger.warning("⚠ Sync fehlgeschlagen")

        logger.info("─" * 60)
        return success

    def run_daemon(self, interval: int = DEFAULT_INTERVAL):
        """Läuft als Daemon"""
        logger.info(f"Daemon gestartet - Intervall: {interval}s")

        # Initiale Sync
        self.sync()

        # Endlosschleife
        while not self.stop_event.is_set():
            try:
                time.sleep(interval)
                if not self.stop_event.is_set():
                    self.sync()
            except KeyboardInterrupt:
                logger.info("Daemon beendet")
                break


# ============================================================================
# WEB-INTERFACE
# ============================================================================

class SetupHTTPHandler(SimpleHTTPRequestHandler):
    """HTTP Handler für Setup und Status"""

    config_manager = None
    syncer = None

    def do_GET(self):
        """GET Requests"""
        if self.path == '/':
            self._serve_setup_html()
        elif self.path == '/status':
            self._serve_status_json()
        elif self.path == '/api/test-connection':
            self._test_3cx_connection()
        elif self.path == '/phonebook.csv' or self.path == '/phonebook.xml':
            super().do_GET()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """POST Requests"""
        if self.path == '/api/config/save':
            self._save_configuration()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_setup_html(self):
        """Zeigt Setup-HTML"""
        html = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3CX → Yealink Setup</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 100%;
            padding: 40px;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            color: #333;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 14px;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
            font-family: inherit;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 30px;
        }
        button {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-test {
            background: #f0f0f0;
            color: #333;
        }
        .btn-test:hover {
            background: #e0e0e0;
        }
        .btn-save {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-save:hover {
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        .status {
            margin-top: 20px;
            padding: 12px;
            border-radius: 6px;
            font-size: 13px;
            display: none;
        }
        .status.success {
            background: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #a5d6a7;
            display: block;
        }
        .status.error {
            background: #ffebee;
            color: #c62828;
            border: 1px solid #ef9a9a;
            display: block;
        }
        .status.info {
            background: #e3f2fd;
            color: #1565c0;
            border: 1px solid #90caf9;
            display: block;
        }
        .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(0,0,0,0.1);
            border-top-color: currentColor;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .help-text {
            font-size: 12px;
            color: #999;
            margin-top: 4px;
        }
        .success-banner {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
            display: none;
        }
        .success-banner.show {
            display: block;
        }
        .success-banner strong {
            color: #2e7d32;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 3CX Setup</h1>
        <p class="subtitle">Verbinden Sie Ihre 3CX-Telefonanlage mit Yealink-Telefonen</p>

        <div class="success-banner" id="successBanner">
            <strong>✓ Erfolgreich konfiguriert!</strong><br>
            Das System synchronisiert Kontakte jetzt automatisch.
        </div>

        <form id="setupForm">
            <div class="form-group">
                <label for="fqdn">3CX Hostname/FQDN</label>
                <input type="text" id="fqdn" placeholder="z.B. 3cx.example.com oder 192.168.1.10" required>
                <div class="help-text">FQDN oder IP-Adresse der 3CX-Anlage</div>
            </div>

            <div class="form-group">
                <label for="extension">Nebenstelle (Extension)</label>
                <input type="text" id="extension" placeholder="z.B. 101" required>
                <div class="help-text">Ihre Admin-Nebenstelle oder Systemeigentümer-Extension</div>
            </div>

            <div class="form-group">
                <label for="password">Passwort</label>
                <input type="password" id="password" placeholder="Passwort für die Nebenstelle" required>
                <div class="help-text">Wird verschlüsselt gespeichert</div>
            </div>

            <div class="button-group">
                <button type="button" class="btn-test" id="testBtn">🧪 Verbindung testen</button>
                <button type="submit" class="btn-save">💾 Speichern & Starten</button>
            </div>

            <div class="status" id="status"></div>
        </form>
    </div>

    <script>
        const form = document.getElementById('setupForm');
        const testBtn = document.getElementById('testBtn');
        const statusDiv = document.getElementById('status');
        const successBanner = document.getElementById('successBanner');

        // Gespeicherte Werte laden
        function loadConfig() {
            fetch('/api/config')
                .then(r => r.json())
                .then(config => {
                    if (config.fqdn) document.getElementById('fqdn').value = config.fqdn;
                    if (config.extension) document.getElementById('extension').value = config.extension;
                    if (config.last_sync) {
                        showStatus('success', `✓ Letzte Synchronisation: ${new Date(config.last_sync).toLocaleString('de-DE')}`);
                        successBanner.classList.add('show');
                    }
                })
                .catch(e => console.log('Config nicht verfügbar'));
        }

        function showStatus(type, message) {
            statusDiv.className = 'status ' + type;
            statusDiv.textContent = message;
        }

        testBtn.addEventListener('click', async () => {
            const fqdn = document.getElementById('fqdn').value;
            const extension = document.getElementById('extension').value;
            const password = document.getElementById('password').value;

            if (!fqdn || !extension || !password) {
                showStatus('error', '⚠ Alle Felder erforderlich!');
                return;
            }

            testBtn.disabled = true;
            testBtn.innerHTML = '<span class="spinner"></span>Teste...';
            showStatus('info', '🔄 Verbindung wird getestet...');

            try {
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fqdn, extension, password })
                });
                const data = await response.json();
                showStatus(data.success ? 'success' : 'error', data.message);
            } catch (e) {
                showStatus('error', '✗ Verbindungsfehler: ' + e.message);
            } finally {
                testBtn.disabled = false;
                testBtn.innerHTML = '🧪 Verbindung testen';
            }
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const fqdn = document.getElementById('fqdn').value;
            const extension = document.getElementById('extension').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/config/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fqdn, extension, password })
                });
                const data = await response.json();

                if (data.success) {
                    showStatus('success', '✓ Konfiguration gespeichert! System synchronisiert automatisch.');
                    successBanner.classList.add('show');
                    setTimeout(() => location.reload(), 2000);
                } else {
                    showStatus('error', '✗ Fehler: ' + (data.message || 'Unbekannter Fehler'));
                }
            } catch (e) {
                showStatus('error', '✗ Fehler beim Speichern: ' + e.message);
            }
        });

        // Beim Laden
        loadConfig();
    </script>
</body>
</html>"""

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _serve_status_json(self):
        """Liefert Status als JSON"""
        status = {
            'service': 'running',
            'last_sync': self.syncer.last_sync if self.syncer else None,
            'contact_count': self.syncer.contact_count if self.syncer else 0,
            'timestamp': datetime.now().isoformat(),
            'mode': self.config_manager.get('mode', 'api') if self.config_manager else 'unknown'
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(status, ensure_ascii=False).encode('utf-8'))

    def _test_3cx_connection(self):
        """Testet 3CX-Verbindung"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            client = ThreeCXAPIClient(
                fqdn=data.get('fqdn'),
                extension=data.get('extension'),
                password=data.get('password')
            )

            success, message = client.test_connection()

            response = {
                'success': success,
                'message': message
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'message': str(e)}).encode())

    def _save_configuration(self):
        """Speichert Konfiguration"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            config = self.config_manager.config.copy()
            config['3cx_fqdn'] = data.get('fqdn')
            config['3cx_extension'] = data.get('extension')
            config['3cx_password'] = self.config_manager.encrypt_password(data.get('password'))
            config['mode'] = 'api'

            if self.config_manager.save_config(config):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'message': '✓ Konfiguration gespeichert'}).encode())
            else:
                raise Exception('Fehler beim Speichern')

        except Exception as e:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'message': str(e)}).encode())

    def log_message(self, format, *args):
        """Überschreibt HTTP-Logging"""
        logger.debug(f"HTTP: {format % args}")


# ============================================================================
# HAUPTPROGRAMM
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='3CX → Yealink AX Phonebook Sync Service (PRO)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--setup',
        action='store_true',
        help='Starte nur Setup-Interface (auf Port 8080)'
    )
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Starte als Daemon mit Synchronisation'
    )
    parser.add_argument(
        '--config',
        default=CONFIG_FILE,
        help=f'Pfad zur Konfigurationsdatei (Standard: {CONFIG_FILE})'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=DEFAULT_PORT,
        help=f'HTTP-Port (Standard: {DEFAULT_PORT})'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=DEFAULT_INTERVAL,
        help=f'Sync-Intervall in Sekunden (Standard: {DEFAULT_INTERVAL})'
    )
    parser.add_argument(
        '--log-file',
        help='Log-Datei (optional)'
    )

    args = parser.parse_args()

    # Config laden
    config_manager = ConfigManager(args.config)

    # Setup-Mode
    if args.setup:
        logger.info(f"Setup-Interface läuft auf Port {args.port}")
        logger.info(f"Öffnen Sie im Browser: http://localhost:{args.port}")

        os.chdir(config_manager.get('output_dir', OUTPUT_DIR))
        os.makedirs(config_manager.get('output_dir', OUTPUT_DIR), exist_ok=True)

        server = HTTPServer(('0.0.0.0', args.port), SetupHTTPHandler)
        SetupHTTPHandler.config_manager = config_manager
        SetupHTTPHandler.syncer = None

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Setup beendet")

    # Daemon-Mode
    elif args.daemon:
        syncer = PhonebookSyncer(config_manager)

        # HTTP-Server starten (im Hintergrund)
        os.chdir(config_manager.get('output_dir', OUTPUT_DIR))
        os.makedirs(config_manager.get('output_dir', OUTPUT_DIR), exist_ok=True)

        server = HTTPServer(('0.0.0.0', args.port), SetupHTTPHandler)
        SetupHTTPHandler.config_manager = config_manager
        SetupHTTPHandler.syncer = syncer

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        logger.info(f"HTTP-Server läuft auf Port {args.port}")

        # Synchronisationsdaemon
        syncer.run_daemon(interval=args.interval)

    else:
        # Interaktiver Modus
        parser.print_help()
        logger.info("\nBeispiele:")
        logger.info("  python3 3cx_yealink_sync_pro.py --setup")
        logger.info("  python3 3cx_yealink_sync_pro.py --daemon")


if __name__ == '__main__':
    main()
