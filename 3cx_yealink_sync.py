#!/usr/bin/env python3
"""
3CX → Yealink AX Series Phonebook Sync Service
Synchronisiert das 3CX-Firmentelefonbuch mit den Yealink AX83H/AX86R Telefonen

Features:
- Liest 3CX-CSV-Export mit beliebig vielen Kontakten
- Mappt alle 4 Nummernfelder optimal auf Yealink AX Format
- Bietet Datei via HTTP für Remote-Phonebook-Link
- Läuft als Daemon mit regelmäßiger Synchronisation
- Logging + Error-Handling
- CSV oder XML-Ausgabe

Mapping der 4 Yealink-Felder:
  1. office_number  ← Business (primär) / Business2 (fallback)
  2. mobile_number  ← Mobile (primär)
  3. other_number   ← Mobile2 (primär) / Home (fallback)
  4. businessFax    ← BusinessFax (primär) / Other (fallback)
"""

import csv
import json
import logging
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import signal


# ============================================================================
# KONFIGURATION
# ============================================================================

DEFAULT_INTERVAL = 300  # Sekunden zwischen Sync-Läufen (5 Minuten)
DEFAULT_PORT = 8080
DEFAULT_FORMAT = "csv"  # oder "xml"


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_file=None):
    """Konfiguriert Logging zu Datei und Konsole"""
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    log_level = logging.INFO

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Konsolen-Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # Datei-Handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

    return logger


logger = setup_logging()


# ============================================================================
# CSV-VERARBEITUNG
# ============================================================================

def read_3cx_csv(csv_path):
    """
    Liest 3CX-CSV und gibt Liste von Kontakt-Dicts zurück.

    Erwartet Header: FirstName, LastName, Company, Mobile, Mobile2,
                     Business, Business2, Home, Other, BusinessFax, Pager, Email
    """
    contacts = []

    if not os.path.exists(csv_path):
        logger.error(f"CSV-Datei nicht gefunden: {csv_path}")
        return contacts

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                logger.error("CSV hat keinen Header")
                return contacts

            for row_idx, row in enumerate(reader, start=2):  # Start bei 2 wegen Header
                try:
                    contact = parse_3cx_row(row)
                    if contact:
                        contacts.append(contact)
                except Exception as e:
                    logger.warning(f"Fehler bei Zeile {row_idx}: {e}")
                    continue

        logger.info(f"✓ {len(contacts)} Kontakte aus {csv_path} gelesen")
        return contacts

    except Exception as e:
        logger.error(f"Fehler beim Lesen der CSV: {e}")
        return []


def parse_3cx_row(row):
    """
    Parst eine 3CX-CSV-Zeile und gibt einen Kontakt-Dict mit allen Feldern zurück.
    """
    # Extrahiere Basis-Informationen
    first_name = (row.get('FirstName') or '').strip()
    last_name = (row.get('LastName') or '').strip()
    company = (row.get('Company') or '').strip()
    email = (row.get('Email') or '').strip()

    # display_name: Company wenn vorhanden, sonst FirstName LastName
    display_name = company if company else f"{first_name} {last_name}".strip()

    if not display_name:
        return None  # Kontakt ohne Namen ignorieren

    # Extrahiere Nummernfelder (alle verfügbaren Typen)
    phone_data = {
        'Mobile': (row.get('Mobile') or '').strip(),
        'Mobile2': (row.get('Mobile2') or '').strip(),
        'Business': (row.get('Business') or '').strip(),
        'Business2': (row.get('Business2') or '').strip(),
        'Home': (row.get('Home') or '').strip(),
        'Other': (row.get('Other') or '').strip(),
        'BusinessFax': (row.get('BusinessFax') or '').strip(),
        'Pager': (row.get('Pager') or '').strip(),
    }

    # Mapping auf die 4 Yealink-Felder (intelligent, mit Fallback)
    contact = {
        'display_name': display_name,
        'company': company,
        'email': email,
        'office_number': phone_data['Business'] or phone_data['Business2'] or '',
        'mobile_number': phone_data['Mobile'] or '',
        'other_number': phone_data['Mobile2'] or phone_data['Home'] or '',
        'businessFax': phone_data['BusinessFax'] or phone_data['Other'] or '',
    }

    # Nur Kontakte mit mindestens einer Nummer behalten
    has_numbers = any([
        contact['office_number'],
        contact['mobile_number'],
        contact['other_number'],
        contact['businessFax']
    ])

    return contact if has_numbers else None


# ============================================================================
# CSV-EXPORT (Yealink AX Format)
# ============================================================================

def write_yealink_csv(contacts, output_path):
    """
    Schreibt Kontakte im Yealink AX Format als CSV.

    Format entspricht: display_name,office_number,mobile_number,other_number,
                       businessFax,line,ring,auto_divert,priority,group_id_name,
                       default_photo,photo_data
    """
    try:
        fieldnames = [
            'display_name',
            'office_number',
            'mobile_number',
            'other_number',
            'businessFax',
            'line',
            'ring',
            'auto_divert',
            'priority',
            'group_id_name',
            'default_photo',
            'photo_data'
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
                    'line': -1,  # Standard
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


# ============================================================================
# XML-EXPORT (VP Contact Format - optional)
# ============================================================================

def write_yealink_xml(contacts, output_path):
    """
    Schreibt Kontakte im vp_contact-XML-Format für Yealink-Telefone.
    """
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

        xml_lines.extend([
            '  </root_contact>',
            '</vp_contact>'
        ])

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_lines))

        logger.info(f"✓ XML geschrieben: {output_path} ({len(contacts)} Kontakte)")
        return True

    except Exception as e:
        logger.error(f"Fehler beim Schreiben der XML: {e}")
        return False


def escape_xml(text):
    """Escaped XML-Sonderzeichen"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))


# ============================================================================
# HTTP-SERVER
# ============================================================================

class PhonebookHTTPHandler(SimpleHTTPRequestHandler):
    """HTTP-Handler für die Phonebook-Datei"""

    def do_GET(self):
        """Behandelt GET-Requests"""
        if self.path == '/' or self.path == '':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>3CX ↔ Yealink Phonebook Sync</title></head>
            <body>
            <h1>3CX → Yealink Phonebook Sync Service</h1>
            <p>Service läuft. Verfügbare Dateien:</p>
            <ul>
            <li><a href="/phonebook.csv">phonebook.csv</a></li>
            <li><a href="/phonebook.xml">phonebook.xml</a></li>
            <li><a href="/status">Status-Info</a></li>
            </ul>
            </body>
            </html>
            """
            self.wfile.write(html.encode())

        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = {
                'service': 'running',
                'last_sync': getattr(self.server, 'last_sync', 'never'),
                'contact_count': getattr(self.server, 'contact_count', 0),
                'timestamp': datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(status, indent=2, ensure_ascii=False).encode('utf-8'))

        else:
            # Standard-Datei-Serving
            super().do_GET()

    def log_message(self, format, *args):
        """Überschreibt Logging für HTTP-Requests"""
        logger.debug(f"HTTP {format % args}")


def start_http_server(output_dir, port):
    """Startet HTTP-Server in eigenem Thread"""
    os.chdir(output_dir)

    try:
        server = HTTPServer(('0.0.0.0', port), PhonebookHTTPHandler)
        logger.info(f"✓ HTTP-Server läuft auf Port {port}")

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        return server

    except Exception as e:
        logger.error(f"Fehler beim Starten des HTTP-Servers: {e}")
        return None


# ============================================================================
# SYNC-LOGIK
# ============================================================================

def sync_phonebook(input_csv, output_dir, format_type='csv', http_server=None):
    """
    Führt einen Sync-Lauf durch:
    1. Liest 3CX-CSV
    2. Parscht und mappt Kontakte
    3. Schreibt Ausgabedatei(en)
    4. Aktualisiert HTTP-Server-Status
    """
    logger.info("─" * 60)
    logger.info(f"Sync-Lauf gestartet: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # CSV lesen
    contacts = read_3cx_csv(input_csv)

    if not contacts:
        logger.warning("Keine Kontakte geladen!")
        return False

    # Ausgabeverzeichnis erstellen
    os.makedirs(output_dir, exist_ok=True)

    # CSV schreiben
    csv_output = os.path.join(output_dir, 'phonebook.csv')
    if not write_yealink_csv(contacts, csv_output):
        return False

    # XML schreiben (immer für Flexibilität)
    xml_output = os.path.join(output_dir, 'phonebook.xml')
    if not write_yealink_xml(contacts, xml_output):
        return False

    # HTTP-Server aktualisieren
    if http_server:
        http_server.last_sync = datetime.now().isoformat()
        http_server.contact_count = len(contacts)

    logger.info(f"✓ Sync erfolgreich: {len(contacts)} Kontakte verarbeitet")
    logger.info("─" * 60)

    return True


def run_sync_daemon(input_csv, output_dir, interval=DEFAULT_INTERVAL, port=DEFAULT_PORT):
    """
    Läuft als Daemon und synchronisiert regelmäßig.
    """
    logger.info(f"Daemon gestartet - Sync-Intervall: {interval}s, HTTP-Port: {port}")

    # HTTP-Server starten
    http_server = start_http_server(output_dir, port)

    # Initiale Synchronisation
    sync_phonebook(input_csv, output_dir, http_server=http_server)

    # Endlosschleife
    try:
        while True:
            time.sleep(interval)
            sync_phonebook(input_csv, output_dir, http_server=http_server)

    except KeyboardInterrupt:
        logger.info("Daemon wurde beendet (SIGINT)")
    except Exception as e:
        logger.error(f"Daemon-Fehler: {e}")


# ============================================================================
# CLI & HAUPTPROGRAMM
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='3CX → Yealink AX Series Phonebook Sync Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # Als Daemon mit CSV-Ausgabe
  python3 3cx_yealink_sync.py \\
    --input /var/lib/3cx/phonebook/contacts_3cx.csv \\
    --output /var/www/html/phonebook \\
    --interval 300 \\
    --port 8080

  # Einmalige Synchronisation
  python3 3cx_yealink_sync.py \\
    --input /path/to/contacts.csv \\
    --output /path/to/output \\
    --once
        """
    )

    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Pfad zur 3CX-CSV-Datei'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Ausgabeverzeichnis für phonebook.csv und phonebook.xml'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=DEFAULT_INTERVAL,
        help=f'Sync-Intervall in Sekunden (Standard: {DEFAULT_INTERVAL})'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=DEFAULT_PORT,
        help=f'HTTP-Port für Phonebook-Link (Standard: {DEFAULT_PORT})'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['csv', 'xml', 'both'],
        default='both',
        help='Ausgabeformat (Standard: both)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Nur einmalige Synchronisation (kein Daemon)'
    )
    parser.add_argument(
        '--log-file',
        help='Optionale Log-Datei'
    )

    args = parser.parse_args()

    # Logging einrichten
    if args.log_file:
        setup_logging(args.log_file)

    # Hauptprogramm
    if args.once:
        # Einmalig
        logger.info(f"Input: {args.input}")
        logger.info(f"Output: {args.output}")
        sync_phonebook(args.input, args.output, format_type=args.format)
    else:
        # Daemon
        logger.info(f"Input: {args.input}")
        logger.info(f"Output: {args.output}")
        logger.info(f"HTTP-Port: {args.port}")
        logger.info(f"Intervall: {args.interval}s")
        run_sync_daemon(args.input, args.output, interval=args.interval, port=args.port)


if __name__ == '__main__':
    main()
