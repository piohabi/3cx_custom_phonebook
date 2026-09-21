#!/usr/bin/env python3
"""ProOffice 3CX Phonebook Server — pulls company contacts from a 3CX PBX via XAPI and
publishes a Yealink Remote Phone Book XML (Phone1..Phone4 per contact) at a fixed URL.

Field names below are confirmed live 2026-08-30 against pro-office-test.on3cx.de (PBX
20.0.9.995): logged in via the same WebClient endpoint 3CX's own web client uses, fetched
GET /xapi/v1/$metadata, and round-tripped a POST/DELETE against /xapi/v1/Contacts to see
the real shape (Contacts was empty on that system, so this was the only way to confirm
without guessing). See CONTEXT.md for the full trail. Real Contact fields differ from the
originally assumed ones: there is no plain "Mobile" — the primary number field is
"PhoneNumber" — and the company name field is "CompanyName", not "Company".
"""

import hashlib
import hmac
import html
import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.parse
import re
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.sax.saxutils import escape

import requests
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
log = logging.getLogger("phonebook")

CONFIG_PATH = os.environ.get("PHONEBOOK_CONFIG", "config.yml")
ENV_PATH = os.environ.get("PHONEBOOK_ENV", ".env")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Passwort bewusst NICHT in config.yml — kommt separat aus der Umgebung (.env, siehe
    # README.md), damit es nicht versehentlich mit der (ansonsten unkritischen) Konfig
    # committed/kopiert wird.
    cfg["threecx"]["password"] = os.environ["THREECX_PASSWORD"]
    # Zugriffs-Token fürs Telefonbuch selbst — der Dienst läuft auf einer öffentlich
    # erreichbaren VM, ohne diesen Schutz könnte jeder im Internet die Kontaktliste abrufen.
    cfg["server"]["access_token"] = os.environ["PHONEBOOK_ACCESS_TOKEN"]
    return cfg


class ThreeCXClient:
    """Meldet sich wie der 3CX-WebClient an (POST /webclient/api/Login/GetAccessToken),
    cached den Bearer-Token bis kurz vor Ablauf und liest /xapi/v1/Contacts seitenweise
    über $top/$skip aus. Ein einzelner erzwungener Re-Login-Versuch bei 401 fängt den Fall
    ab, dass der Token serverseitig vorzeitig ungültig wurde (z. B. manuelles Abmelden
    dieses Kontos in der 3CX-Konsole)."""

    # Confirmed live 2026-08-30: this 3CX system enforces a hard server-side cap of 100 on
    # $top ("The limit of '100' for Top query has been exceeded" for anything higher) —
    # not documented anywhere, found by trial. Paging still works fine below 100.
    PAGE_SIZE = 100

    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token = None
        self._expires_at = 0

    def _login(self):
        resp = requests.post(
            f"{self.base_url}/webclient/api/Login/GetAccessToken",
            json={"Username": self.username, "Password": self.password, "SecurityCode": ""},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("Status") and body["Status"] != "AuthSuccess":
            raise RuntimeError(f"3CX-Anmeldung fehlgeschlagen: {body['Status']}")
        token = body["Token"]
        self._token = token["access_token"]
        # 60s Sicherheitsabstand vor dem echten Ablauf, damit ein Sync-Lauf nicht mitten
        # in der Ausführung mit einem gerade abgelaufenen Token gegen die API läuft.
        self._expires_at = time.time() + token["expires_in"] - 60
        log.info("3CX-Login erfolgreich (PBX-Version %s)", token.get("pbx_version", "?"))

    def _ensure_token(self):
        if not self._token or time.time() >= self._expires_at:
            self._login()

    def fetch_contacts(self):
        self._ensure_token()
        contacts = []
        skip = 0
        while True:
            resp = self._get_contacts_page(skip)
            if resp.status_code == 401:
                self._login()
                resp = self._get_contacts_page(skip)
            resp.raise_for_status()
            page = resp.json().get("value", [])
            contacts.extend(page)
            if len(page) < self.PAGE_SIZE:
                break
            skip += self.PAGE_SIZE
        return contacts

    def _get_contacts_page(self, skip):
        return requests.get(
            f"{self.base_url}/xapi/v1/Contacts?$top={self.PAGE_SIZE}&$skip={skip}",
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=20,
        )


# Reihenfolge bestimmt, welche 4 Nummern ein Kontakt im Yealink-Telefonbuch bekommt, falls
# mehr als 4 Felder belegt sind (Yealinks Remote-Phonebook-Format kennt nur Phone1..Phone4,
# siehe build_yealink_xml()'s Doc). PhoneNumber zuerst (3CX' "Haupt"-Nummernfeld), dann die
# geschäftlichen Nummern, dann die übrigen. BusinessFax/Pager stehen bewusst zuletzt — ein
# Faxgerät oder einen Pager aus dem Telefonbuch anzurufen ist selten hilfreich, wenn ohnehin
# schon 4 andere Nummern belegt sind.
NUMBER_FIELDS_IN_PRIORITY = ["PhoneNumber", "Business", "Mobile2", "Business2", "Home", "Other", "BusinessFax", "Pager"]


def normalize_number(value, settings=None):
    settings = settings or {}
    value = value.strip()
    if not settings.get("normalize_numbers"):
        return value
    value = re.sub(r"[^0-9+]", "", value)
    country_code = str(settings.get("country_code", "+49")).strip()
    if value.startswith("00"):
        value = "+" + value[2:]
    elif value.startswith("0") and country_code:
        value = country_code + value[1:]
    return value


def contact_numbers(contact, settings=None):
    settings = settings or {}
    fields = settings.get("number_fields") or NUMBER_FIELDS_IN_PRIORITY
    numbers = []
    for field in fields:
        value = normalize_number(str(contact.get(field) or ""), settings)
        if value and value not in numbers:
            numbers.append(value)
        if len(numbers) == 4:
            break
    return numbers


def contact_display_name(contact):
    company = (contact.get("CompanyName") or "").strip()
    if company:
        return company
    parts = [p for p in [(contact.get("FirstName") or "").strip(), (contact.get("LastName") or "").strip()] if p]
    return " ".join(parts) or "Unbenannt"


def prepare_contacts(contacts, settings):
    if not settings.get("deduplicate"):
        return contacts
    result, seen = [], set()
    for contact in contacts:
        key = (contact_display_name(contact).casefold(), tuple(contact_numbers(contact, settings)))
        if key in seen:
            continue
        seen.add(key)
        result.append(contact)
    return result


def build_yealink_xml(contacts, group_name, settings=None):
    """YealinkIPPhoneBook — das Remote-Phone-Book-Format aus Yealinks Auto-Provisioning-
    Guide (identisches Schema für AX83H/AX86R wie für alle aktuellen Yealink-SIP-Telefone/
    DECT-Basisstationen). Bis zu 4 Nummern pro <Unit> (Phone1..Phone4) — deckt reale 3CX-
    Contacts-Daten ab, da ein Contact-Datensatz höchstens 8 nummernartige Felder hat und die
    meisten davon unbelegt sind (siehe contact_numbers()'s Doc zur Prioritätsreihenfolge,
    falls doch mehr als 4 belegt sind)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<YealinkIPPhoneBook>", f"<Menu><Name>{escape(group_name)}</Name>"]
    skipped = 0
    settings = settings or {}
    for contact in prepare_contacts(contacts, settings):
        numbers = contact_numbers(contact, settings)
        if not numbers:
            skipped += 1
            continue
        name = escape(contact_display_name(contact))
        lines.append("<Unit>")
        lines.append(f"<Name>{name}</Name>")
        for i in range(4):
            lines.append(f"<Phone{i + 1}>{escape(numbers[i]) if i < len(numbers) else ''}</Phone{i + 1}>")
        lines.append("</Unit>")
    lines.append("</Menu>")
    lines.append("</YealinkIPPhoneBook>")
    if skipped:
        log.info("%d Kontakt(e) ohne jede Rufnummer übersprungen", skipped)
    return "\n".join(lines)


class SyncState:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_sync = None
        self.last_error = None
        self.contact_count = 0
        self.number_count = 0
        self.xml_hash = None
        self.connected = False
        self.contacts = []
        self.sync_requested = threading.Event()

    def snapshot(self):
        with self.lock:
            return dict(
                connected=self.connected,
                last_sync=self.last_sync,
                last_error=self.last_error,
                contact_count=self.contact_count,
                number_count=self.number_count,
            )

    def contacts_snapshot(self):
        with self.lock:
            return list(self.contacts)

    def request_sync(self):
        self.sync_requested.set()


def atomic_write(path, content):
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    # os.replace ist auf demselben Dateisystem atomar — ein Telefon, das genau in diesem
    # Moment pollt, sieht entweder die alte oder die neue Datei, nie eine halb geschriebene.
    os.replace(tmp_path, path)


def update_env_value(path, name, value):
    """Aktualisiert genau eine Variable, ohne Token oder andere Werte zu verändern."""
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    replacement = f"{name}={value}"
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(f"{name}="):
            lines[index] = replacement
            replaced = True
            break
    if not replaced:
        lines.append(replacement)
    write_settings_file(path, "\n".join(lines) + "\n")


def write_settings_file(path, content):
    """Schreibt vom Systemd-Sandboxing einzeln freigegebene Einstellungsdateien.

    Deren Verzeichnis bleibt absichtlich schreibgeschützt; daher kann dort keine
    temporäre Datei für os.replace() angelegt werden.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())


def backup_settings():
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(CONFIG_PATH)), "logs")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for source, label in ((CONFIG_PATH, "config"), (ENV_PATH, "env")):
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(backup_dir, f"{label}-{stamp}.bak"))


def sync_loop(cfg, state, stop_event):
    client = ThreeCXClient(cfg["threecx"]["url"], cfg["threecx"]["username"], cfg["threecx"]["password"])
    output_path = cfg["server"]["phonebook_path"]
    group_name = cfg.get("yealink", {}).get("group_name", "3CX Kontakte")
    yealink_settings = cfg.get("yealink", {})
    interval = cfg["sync"]["interval"]

    while not stop_event.is_set():
        try:
            contacts = client.fetch_contacts()
            xml = build_yealink_xml(contacts, group_name, yealink_settings)
            digest = hashlib.sha256(xml.encode("utf-8")).hexdigest()
            with state.lock:
                changed = digest != state.xml_hash
            if changed:
                atomic_write(output_path, xml)
                log.info("Telefonbuch aktualisiert (%d Kontakte)", len(contacts))
            with state.lock:
                state.connected = True
                state.last_error = None
                state.last_sync = time.strftime("%Y-%m-%d %H:%M:%S")
                state.contact_count = len(contacts)
                state.number_count = sum(len(contact_numbers(c, yealink_settings)) for c in contacts)
                state.xml_hash = digest
                state.contacts = list(contacts)
        except Exception as exc:  # noqa: BLE001 — ein einzelner fehlgeschlagener Sync darf
            # den Dienst nie beenden, nur Status/Log widerspiegeln; der nächste Intervall-
            # Lauf versucht es automatisch erneut.
            log.error("Sync fehlgeschlagen: %s", exc)
            with state.lock:
                state.connected = False
                state.last_error = str(exc)
        state.sync_requested.wait(interval)
        state.sync_requested.clear()


def make_handler(cfg, state):
    phonebook_path = cfg["server"]["phonebook_path"]
    access_token = cfg["server"]["access_token"]
    allowed_ips = set(cfg["server"].get("allowed_ips", []))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 (shadows builtin `format`, matches BaseHTTPRequestHandler's own signature)
            log.info("%s - %s", self.address_string(), format % args)

        def do_GET(self):
            if allowed_ips and self.client_address[0] not in allowed_ips:
                log.warning("Zugriff von nicht freigegebener IP %s abgelehnt", self.client_address[0])
                self.send_error(403, "IP-Adresse nicht freigegeben")
                return
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/":
                self.send_response(302)
                self.send_header("Location", f"/admin?key={urllib.parse.quote(access_token, safe='')}")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
            elif path == "/phonebook.xml":
                if not self._authorized(parsed):
                    log.warning("Unautorisierter Zugriff von %s abgelehnt", self.address_string())
                    self.send_error(403, "Fehlender oder falscher Zugriffs-Token")
                    return
                self._serve_phonebook()
            elif path == "/phonebook-group.xml":
                if not self._authorized(parsed):
                    self.send_error(403, "Fehlender oder falscher Zugriffs-Token")
                    return
                self._serve_phonebook_group(parsed)
            elif path == "/admin":
                if not self._authorized(parsed):
                    self.send_error(403, "Fehlender oder falscher Zugriffs-Token")
                    return
                self._serve_admin(parsed)
            elif path in ("/status", "/status.json"):
                self._serve_status()
            elif path == "/contacts":
                if not self._authorized(parsed):
                    self.send_error(403, "Fehlender oder falscher Zugriffs-Token")
                    return
                self._serve_contacts(parsed)
            elif path == "/yealink-preview":
                if not self._authorized(parsed):
                    self.send_error(403, "Fehlender oder falscher Zugriffs-Token")
                    return
                self._serve_yealink_preview()
            elif path == "/raw-contacts":
                if not self._authorized(parsed):
                    self.send_error(403, "Fehlender oder falscher Zugriffs-Token")
                    return
                self._serve_raw_contacts(parsed)
            else:
                self.send_error(404)

        def do_POST(self):
            if allowed_ips and self.client_address[0] not in allowed_ips:
                self.send_error(403, "IP-Adresse nicht freigegeben")
                return
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path not in ("/admin", "/sync-now", "/test-connection") or not self._authorized(parsed):
                self.send_error(403, "Fehlender oder falscher Zugriffs-Token")
                return
            if parsed.path == "/sync-now":
                state.request_sync()
                self._send_html(self._admin_page("Synchronisierung wurde gestartet."))
                return
            if parsed.path == "/test-connection":
                try:
                    test_client = ThreeCXClient(cfg["threecx"]["url"], cfg["threecx"]["username"], cfg["threecx"]["password"])
                    count = len(test_client.fetch_contacts())
                    self._send_html(self._admin_page(f"Verbindung erfolgreich: {count} Kontakte erreichbar."))
                except Exception as exc:  # noqa: BLE001
                    self._send_html(self._admin_page(f"Verbindung fehlgeschlagen: {exc}"), status=400)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 16384:
                    raise ValueError("Ungültige Formulardaten")
                form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
                url = form.get("url", [""])[0].strip().rstrip("/")
                username = form.get("username", [""])[0].strip()
                password = form.get("password", [""])[0]
                page_title = form.get("page_title", [""])[0].strip()
                interval = max(30, int(form.get("sync_interval", ["300"])[0]))
                group_name = form.get("group_name", ["3CX Kontakte"])[0].strip() or "3CX Kontakte"
                number_fields = [item.strip() for item in form.get("number_fields", [""])[0].split(",") if item.strip()]
                normalize_numbers = form.get("normalize_numbers", [""])[0] == "yes"
                country_code = form.get("country_code", ["+49"])[0].strip()
                deduplicate = form.get("deduplicate", [""])[0] == "yes"
                group_rules = []
                for line in form.get("phonebook_groups", [""])[0].splitlines():
                    parts = [part.strip() for part in line.split("|", 2)]
                    if len(parts) == 3 and all(parts):
                        group_rules.append({"name": parts[0], "field": parts[1], "value": parts[2]})
                if not url.startswith("https://") or not username:
                    raise ValueError("3CX-URL muss mit https:// beginnen; Benutzername ist erforderlich.")

                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved_cfg = yaml.safe_load(f)
                backup_settings()
                saved_cfg["threecx"]["url"] = url
                saved_cfg["threecx"]["username"] = username
                saved_cfg.setdefault("sync", {})["interval"] = interval
                saved_cfg.setdefault("yealink", {})["group_name"] = group_name
                saved_cfg["yealink"]["number_fields"] = number_fields or NUMBER_FIELDS_IN_PRIORITY
                saved_cfg["yealink"]["normalize_numbers"] = normalize_numbers
                saved_cfg["yealink"]["country_code"] = country_code
                saved_cfg["yealink"]["deduplicate"] = deduplicate
                saved_cfg["yealink"]["groups"] = group_rules
                if page_title:
                    saved_cfg["server"]["page_title"] = page_title
                else:
                    saved_cfg["server"].pop("page_title", None)
                write_settings_file(CONFIG_PATH, yaml.safe_dump(saved_cfg, allow_unicode=True, sort_keys=False))
                if password:
                    update_env_value(ENV_PATH, "THREECX_PASSWORD", password)

                body = self._admin_page("Konfiguration gespeichert. Der Dienst startet neu …")
                self._send_html(body)
                threading.Timer(0.5, lambda: os._exit(0)).start()
            except (ValueError, OSError, yaml.YAMLError) as exc:
                self._send_html(self._admin_page(str(exc)), status=400)

        def _authorized(self, parsed):
            # hmac.compare_digest statt "==" — schützt vor Timing-Angriffen, die aus der
            # Antwortzeit auf den Token schließen könnten.
            supplied = urllib.parse.parse_qs(parsed.query).get("key", [""])[0]
            return hmac.compare_digest(supplied, access_token)

        def _serve_phonebook(self):
            if not os.path.exists(phonebook_path):
                self.send_error(503, "Telefonbuch noch nicht erzeugt")
                return
            with open(phonebook_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_phonebook_group(self, parsed):
            query = urllib.parse.parse_qs(parsed.query)
            try:
                index = int(query.get("group", ["-1"])[0])
                rule = cfg.get("yealink", {}).get("groups", [])[index]
                if index < 0:
                    raise IndexError
            except (ValueError, IndexError):
                self.send_error(404, "Telefonbuchgruppe nicht gefunden")
                return
            needle = str(rule["value"]).casefold()
            contacts = [c for c in state.contacts_snapshot() if needle in str(c.get(rule["field"], "")).casefold()]
            body = build_yealink_xml(contacts, rule["name"], cfg.get("yealink", {})).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_status(self):
            body = json.dumps(state.snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_admin(self, _parsed):
            self._send_html(self._admin_page())

        def _admin_page(self, message=""):
            raw_url = str(cfg["threecx"].get("url", ""))
            current_url = html.escape(raw_url, quote=True)
            current_user = html.escape(str(cfg["threecx"].get("username", "")), quote=True)
            key = urllib.parse.quote(access_token, safe="")
            pbx_host = urllib.parse.urlparse(raw_url).hostname or self.headers.get("Host", "").split(":")[0]
            raw_title = str(cfg["server"].get("page_title") or f"{pbx_host} - Kontaktbuch")
            page_title = html.escape(raw_title, quote=True)
            sync_cfg = cfg.get("sync", {})
            yealink_cfg = cfg.get("yealink", {})
            status = state.snapshot()
            status_word = "Verbunden" if status["connected"] else "Nicht verbunden"
            status_class = "ok" if status["connected"] else "error"
            last_sync = html.escape(str(status.get("last_sync") or "Noch nie"))
            last_error = html.escape(str(status.get("last_error") or "–"))
            number_fields_value = html.escape(", ".join(yealink_cfg.get("number_fields") or NUMBER_FIELDS_IN_PRIORITY), quote=True)
            normalize_checked = " checked" if yealink_cfg.get("normalize_numbers") else ""
            deduplicate_checked = " checked" if yealink_cfg.get("deduplicate") else ""
            groups_value = html.escape("\n".join(f"{g.get('name', '')}|{g.get('field', '')}|{g.get('value', '')}" for g in yealink_cfg.get("groups", [])))
            group_links = "".join(
                f'<p><strong>{html.escape(str(group.get("name", "Gruppe")))}</strong><br><input readonly value="http://{html.escape(pbx_host)}:{cfg["server"]["port"]}/phonebook-group.xml?group={index}&amp;key={key}"></p>'
                for index, group in enumerate(yealink_cfg.get("groups", []))
            )
            provisioning_url = html.escape(
                f"http://{pbx_host}:{cfg['server']['port']}/phonebook.xml?key={key}", quote=True
            )
            notice = f'<p class="notice">{html.escape(message)}</p>' if message else ""
            return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(raw_title)}</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f6f8;color:#18212b;margin:0;padding:32px 16px}}
main{{max-width:560px;margin:auto;background:white;padding:28px;border-radius:12px;box-shadow:0 4px 22px #0002}}
h1{{margin-top:0;font-size:1.55rem}}label{{display:block;font-weight:650;margin-top:18px}}
input{{box-sizing:border-box;width:100%;padding:11px;margin-top:6px;border:1px solid #aab3bd;border-radius:6px;font:inherit}}
textarea{{box-sizing:border-box;width:100%;min-height:90px;padding:11px;margin-top:6px;border:1px solid #aab3bd;border-radius:6px;font:inherit}}
button{{margin-top:24px;padding:11px 18px;background:#1769aa;color:white;border:0;border-radius:6px;font-weight:700;cursor:pointer}}
.action{{display:inline-block;margin-top:18px;padding:11px 18px;background:#1769aa;color:white;border-radius:6px;font-weight:700;text-decoration:none}}
.hint{{color:#59636e;font-size:.9rem}}.notice{{padding:10px;background:#e7f4e8;border-radius:6px}}
.linkbox{{display:flex;gap:8px;align-items:center}}.linkbox input{{font-family:ui-monospace,monospace;font-size:.85rem}}
.linkbox button{{margin-top:6px;white-space:nowrap;background:#44515e}}
.status{{display:grid;grid-template-columns:1fr 1fr;gap:8px;background:#f4f6f8;padding:14px;border-radius:8px}}.ok{{color:#18733b;font-weight:700}}.error{{color:#b42318;font-weight:700}}.inline{{display:flex;gap:10px;flex-wrap:wrap}}.inline form{{margin:0}}.inline button{{margin-top:12px}}
</style></head><body><main><h1>3CX Kontaktbuch konfigurieren</h1>{notice}
<p id="action-result" class="notice" hidden></p>
<div class="status"><div>Status</div><div class="{status_class}">{status_word}</div><div>Letzter Sync</div><div>{last_sync}</div><div>Kontakte</div><div>{status['contact_count']}</div><div>Rufnummern</div><div>{status['number_count']}</div><div>Letzter Fehler</div><div>{last_error}</div></div>
<div class="inline"><button type="button" onclick="runAction('/test-connection?key={key}')">Verbindung testen</button><button type="button" onclick="runAction('/sync-now?key={key}')">Jetzt synchronisieren</button></div>
<form method="post" action="/admin?key={key}">
<label for="url">3CX-URL</label><input id="url" name="url" type="url" required value="{current_url}" placeholder="https://firma.on3cx.de">
<label for="username">3CX-Benutzername</label><input id="username" name="username" required value="{current_user}" autocomplete="username">
<label for="password">3CX-Passwort</label><input id="password" name="password" type="password" autocomplete="current-password">
<p class="hint">Leer lassen, um das gespeicherte Passwort beizubehalten.</p>
<label for="page-title">Titel der Seite</label><input id="page-title" name="page_title" value="{page_title}" placeholder="{html.escape(pbx_host)} - Kontaktbuch">
<label for="sync-interval">Synchronisationsintervall (Sekunden)</label><input id="sync-interval" name="sync_interval" type="number" min="30" value="{int(sync_cfg.get('interval', 300))}">
<label for="group-name">Yealink-Gruppenname</label><input id="group-name" name="group_name" value="{html.escape(str(yealink_cfg.get('group_name', '3CX Kontakte')), quote=True)}">
<label for="number-fields">Rufnummernfelder in Prioritätsreihenfolge</label><input id="number-fields" name="number_fields" value="{number_fields_value}"><p class="hint">Kommagetrennt; maximal vier gefüllte Felder werden als Phone1 bis Phone4 ausgegeben.</p>
<label><input style="width:auto" type="checkbox" name="normalize_numbers" value="yes"{normalize_checked}> Rufnummern normalisieren</label>
<label for="country-code">Ländervorwahl für führende Null</label><input id="country-code" name="country_code" value="{html.escape(str(yealink_cfg.get('country_code', '+49')), quote=True)}">
<label><input style="width:auto" type="checkbox" name="deduplicate" value="yes"{deduplicate_checked}> Identische Kontakte in der Yealink-Ausgabe entfernen</label>
<label for="phonebook-groups">Zusätzliche Telefonbuchgruppen</label><textarea id="phonebook-groups" name="phonebook_groups" placeholder="Kunden|Tag|Kunde\nVertrieb|Department|Vertrieb">{groups_value}</textarea><p class="hint">Eine Gruppe pro Zeile: Name|3CX-Feld|Suchwert. Geeignete Felder sind Tag, Department und ContactType.</p>
<button type="submit">Speichern und verbinden</button></form>
<hr style="margin:30px 0;border:0;border-top:1px solid #d8dde2">
<h2 style="font-size:1.15rem">Provisionierung der IP-Telefone</h2>
<label for="provisioning-url">Dynamischer Kontaktbuch-Link</label>
<div class="linkbox"><input id="provisioning-url" readonly value="{provisioning_url}"><button type="button" onclick="copyLink()">Kopieren</button></div>
<p id="copy-result" class="hint">Diesen Link als Remote Phonebook URL im IP-Telefon eintragen.</p>
{group_links}
<a class="action" href="/contacts?key={key}">Alle geladenen Kontakte</a>
<a class="action" href="/yealink-preview?key={key}">Yealink-Vorschau AX83H / AX86R</a>
<a class="action" href="/raw-contacts?key={key}">3CX-Rohdaten ansehen</a>
<script>
async function copyLink(){{const e=document.getElementById('provisioning-url'),r=document.getElementById('copy-result');e.focus();e.select();e.setSelectionRange(0,99999);try{{if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(e.value);else if(!document.execCommand('copy'))throw new Error();r.textContent='Link wurde kopiert.'}}catch(x){{r.textContent='Link ist markiert – bitte Strg+C drücken.'}}}}
async function runAction(url){{const r=document.getElementById('action-result');r.hidden=false;r.textContent='Bitte warten …';try{{const response=await fetch(url,{{method:'POST',cache:'no-store'}});const text=await response.text();const doc=new DOMParser().parseFromString(text,'text/html');const message=doc.querySelector('.notice');r.textContent=message?message.textContent:(response.ok?'Aktion erfolgreich.':'Aktion fehlgeschlagen.')}}catch(error){{r.textContent='Aufruf fehlgeschlagen: '+error.message}}}}
</script>
</main></body></html>"""

        def _serve_contacts(self, parsed):
            contacts = state.contacts_snapshot()
            query = urllib.parse.parse_qs(parsed.query)
            search = query.get("q", [""])[0].strip()
            if search:
                needle = search.casefold()
                contacts = [c for c in contacts if needle in (contact_display_name(c) + " " + " ".join(contact_numbers(c, cfg.get("yealink", {})))).casefold()]
            page_number = max(1, int(query.get("page", ["1"])[0] or "1"))
            page_size = 50
            page_count = max(1, (len(contacts) + page_size - 1) // page_size)
            page_number = min(page_number, page_count)
            visible_contacts = contacts[(page_number - 1) * page_size:page_number * page_size]
            pbx_host = urllib.parse.urlparse(str(cfg["threecx"].get("url", ""))).hostname or "3CX"
            title = str(cfg["server"].get("page_title") or f"{pbx_host} - Kontaktbuch")
            rows = []
            for contact in visible_contacts:
                name = html.escape(contact_display_name(contact))
                numbers = ", ".join(html.escape(number) for number in contact_numbers(contact, cfg.get("yealink", {})))
                rows.append(f"<tr><td>{name}</td><td>{numbers}</td></tr>")
            content = "".join(rows) or '<tr><td colspan="2">Noch keine Kontakte geladen.</td></tr>'
            key = urllib.parse.quote(access_token, safe="")
            encoded_search = urllib.parse.quote(search)
            previous_link = f'<a href="/contacts?key={key}&q={encoded_search}&page={page_number - 1}">← Zurück</a>' if page_number > 1 else ""
            next_link = f'<a href="/contacts?key={key}&q={encoded_search}&page={page_number + 1}">Weiter →</a>' if page_number < page_count else ""
            page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>body{{font-family:system-ui,sans-serif;background:#f4f6f8;color:#18212b;margin:0;padding:32px 16px}}main{{max-width:900px;margin:auto;background:#fff;padding:28px;border-radius:12px;box-shadow:0 4px 22px #0002}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #d8dde2}}a{{color:#1769aa}}</style></head>
<body><main><h1>Alle geladenen Kontakte</h1><p>{len(contacts)} Treffer · Seite {page_number} von {page_count}</p><p><a href="/admin?key={key}">← Zur Konfiguration</a></p><form method="get" action="/contacts"><input type="hidden" name="key" value="{key}"><input name="q" value="{html.escape(search, quote=True)}" placeholder="Name oder Rufnummer suchen"><button type="submit">Suchen</button></form><p>{previous_link} &nbsp; {next_link}</p><table><thead><tr><th>Name/Firma</th><th>Rufnummern</th></tr></thead><tbody>{content}</tbody></table><p>{previous_link} &nbsp; {next_link}</p></main></body></html>"""
            self._send_html(page)

        def _serve_yealink_preview(self):
            contacts = state.contacts_snapshot()
            pbx_host = urllib.parse.urlparse(str(cfg["threecx"].get("url", ""))).hostname or "3CX"
            title = str(cfg["server"].get("page_title") or f"{pbx_host} - Kontaktbuch")
            rows = []
            for contact in contacts:
                numbers = contact_numbers(contact, cfg.get("yealink", {}))
                cells = "".join(f"<td>{html.escape(numbers[i]) if i < len(numbers) else ''}</td>" for i in range(4))
                rows.append(f"<tr><td>{html.escape(contact_display_name(contact))}</td>{cells}</tr>")
            content = "".join(rows) or '<tr><td colspan="5">Noch keine Kontakte geladen.</td></tr>'
            key = urllib.parse.quote(access_token, safe="")
            page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} – Yealink</title><style>body{{font-family:system-ui,sans-serif;background:#f4f6f8;color:#18212b;margin:0;padding:32px 16px}}main{{max-width:1100px;margin:auto;background:#fff;padding:28px;border-radius:12px;box-shadow:0 4px 22px #0002}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #d8dde2}}a{{color:#1769aa}}</style></head>
<body><main><h1>Yealink-Vorschau AX83H / AX86R</h1><p>{len(contacts)} Kontakt(e) als Name und Phone1 bis Phone4</p><p><a href="/admin?key={key}">← Zur Konfiguration</a></p><table><thead><tr><th>Name</th><th>Phone1</th><th>Phone2</th><th>Phone3</th><th>Phone4</th></tr></thead><tbody>{content}</tbody></table></main></body></html>"""
            self._send_html(page)

        def _serve_raw_contacts(self, parsed):
            contacts = state.contacts_snapshot()
            query = urllib.parse.parse_qs(parsed.query)
            search = query.get("q", [""])[0].strip()
            if search:
                needle = search.casefold()
                contacts = [c for c in contacts if needle in json.dumps(c, ensure_ascii=False).casefold()]
            key = urllib.parse.quote(access_token, safe="")
            encoded = html.escape(json.dumps(contacts, ensure_ascii=False, indent=2))
            page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>3CX-Rohdaten</title><style>body{{font-family:system-ui,sans-serif;margin:24px}}pre{{white-space:pre-wrap;background:#f4f6f8;padding:16px;border-radius:8px}}input{{padding:8px;width:320px}}button{{padding:8px}}</style></head><body><h1>3CX-Rohdaten</h1><p>{len(contacts)} Kontakt(e) · <a href="/admin?key={key}">Zur Konfiguration</a></p><form><input type="hidden" name="key" value="{key}"><input name="q" value="{html.escape(search, quote=True)}" placeholder="Rohdaten durchsuchen"><button>Suchen</button></form><pre>{encoded}</pre></body></html>"""
            self._send_html(page)

        def _send_html(self, text, status=200):
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    cfg = load_config()
    state = SyncState()
    stop_event = threading.Event()

    def handle_signal(signum, _frame):
        log.info("Beende (Signal %s) …", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    sync_thread = threading.Thread(target=sync_loop, args=(cfg, state, stop_event), daemon=True)
    sync_thread.start()

    server = ThreadingHTTPServer((cfg["server"]["listen"], cfg["server"]["port"]), make_handler(cfg, state))
    http_thread = threading.Thread(target=server.serve_forever, daemon=True)
    http_thread.start()
    log.info("Höre auf %s:%s", cfg["server"]["listen"], cfg["server"]["port"])

    stop_event.wait()
    server.shutdown()
    server.server_close()
    sync_thread.join(timeout=5)


if __name__ == "__main__":
    main()
