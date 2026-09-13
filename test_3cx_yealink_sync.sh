#!/bin/bash
# Test- und Validierungs-Skript für 3CX → Yealink Sync

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# FUNKTIONEN
# ============================================================================

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  3CX → Yealink AX Phonebook Sync - Test & Validierung         ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
}

check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
        return 0
    else
        echo -e "${RED}✗ $1${NC}"
        return 1
    fi
}

warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

error() {
    echo -e "${RED}✗ FEHLER: $1${NC}"
    exit 1
}

# ============================================================================
# HAUPTPRÜFUNGEN
# ============================================================================

print_header

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "1. Python-Installation:"
python3 --version > /dev/null 2>&1 && check "Python $PYTHON_VERSION installiert" || error "Python 3 nicht gefunden"

echo ""
echo "2. Skript-Datei:"
[ -f "3cx_yealink_sync.py" ] && check "3cx_yealink_sync.py existiert" || error "Skript nicht gefunden"

echo ""
echo "3. Systemd-Service:"
if [ -f "/etc/systemd/system/3cx-yealink-sync.service" ]; then
    check "Service-Datei existiert"
else
    warn "Service-Datei nicht gefunden (/etc/systemd/system/3cx-yealink-sync.service)"
fi

echo ""
echo "4. Ausgabeverzeichnis:"
if [ -d "/var/www/html/phonebook" ]; then
    check "Ausgabeverzeichnis existiert: /var/www/html/phonebook"
    PERMS=$(ls -ld /var/www/html/phonebook | awk '{print $1}')
    echo "   Permissions: $PERMS"
else
    warn "Ausgabeverzeichnis nicht gefunden - wird bei erstem Lauf erstellt"
fi

echo ""
echo "5. 3CX-CSV-Datei:"
if [ -f "/var/lib/3cx/phonebook/contacts_3cx.csv" ]; then
    check "CSV-Datei existiert"
    LINE_COUNT=$(wc -l < /var/lib/3cx/phonebook/contacts_3cx.csv)
    echo "   Zeilen: $LINE_COUNT"

    # Header-Check
    HEADER=$(head -n1 /var/lib/3cx/phonebook/contacts_3cx.csv)
    if [[ "$HEADER" == *"FirstName"* ]] && [[ "$HEADER" == *"Company"* ]] && [[ "$HEADER" == *"Mobile"* ]]; then
        check "CSV hat korrekten Header"
    else
        warn "CSV-Header sieht ungewöhnlich aus. Sollte enthalten: FirstName, LastName, Company, Mobile, Business, ..."
        echo "   Aktueller Header: $HEADER"
    fi
else
    error "CSV-Datei nicht gefunden: /var/lib/3cx/phonebook/contacts_3cx.csv - Bitte zuerst 3CX-Export durchführen!"
fi

echo ""
echo "6. Service-Status:"
if systemctl is-active --quiet 3cx-yealink-sync.service 2>/dev/null; then
    check "Service läuft"
else
    warn "Service läuft nicht (oder nicht installiert)"
fi

echo ""
echo "7. HTTP-Server Port 8080:"
if netstat -tlnp 2>/dev/null | grep -q ":8080 "; then
    check "Port 8080 erreichbar"
elif ss -tlnp 2>/dev/null | grep -q ":8080 "; then
    check "Port 8080 erreichbar"
else
    if [ "$(systemctl is-active 3cx-yealink-sync.service 2>/dev/null)" = "active" ]; then
        warn "Port 8080 nicht erreichbar (Service läuft aber Port gebunden?)"
    else
        warn "Port 8080 nicht gebunden (Service nicht aktiv?)"
    fi
fi

# ============================================================================
# NETZWERK-TEST
# ============================================================================

echo ""
echo "8. HTTP-Erreichbarkeit:"
if curl -s http://localhost:8080/ > /dev/null 2>&1; then
    check "HTTP-Server antwortet auf localhost:8080"
else
    warn "HTTP-Server antwortet nicht (Port freigegeben?)"
fi

echo ""
echo "9. Phonebook-Dateien:"
if [ -f "/var/www/html/phonebook/phonebook.csv" ]; then
    CSV_SIZE=$(du -h /var/www/html/phonebook/phonebook.csv | awk '{print $1}')
    check "phonebook.csv existiert ($CSV_SIZE)"
    CSV_CONTACTS=$(tail -n +2 /var/www/html/phonebook/phonebook.csv | wc -l)
    echo "   Kontakte: $CSV_CONTACTS"
else
    warn "phonebook.csv noch nicht erstellt (erste Sync ausstehend?)"
fi

if [ -f "/var/www/html/phonebook/phonebook.xml" ]; then
    XML_SIZE=$(du -h /var/www/html/phonebook/phonebook.xml | awk '{print $1}')
    check "phonebook.xml existiert ($XML_SIZE)"
else
    warn "phonebook.xml noch nicht erstellt"
fi

# ============================================================================
# LOG-ANALYSE
# ============================================================================

echo ""
echo "10. Letzte Log-Einträge:"
if systemctl is-active --quiet 3cx-yealink-sync.service 2>/dev/null; then
    echo ""
    journalctl -u 3cx-yealink-sync.service -n 5 --no-pager | sed 's/^/   /'
fi

# ============================================================================
# STATUS-API TEST
# ============================================================================

echo ""
echo "11. Status-API:"
STATUS_OUTPUT=$(curl -s http://localhost:8080/status 2>/dev/null || echo "")
if [ -n "$STATUS_OUTPUT" ]; then
    check "Status-API antwortet"
    echo "   $(echo "$STATUS_OUTPUT" | head -n 1)"
else
    warn "Status-API nicht erreichbar"
fi

# ============================================================================
# EMPFEHLUNGEN
# ============================================================================

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Nächste Schritte                                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✓ Skript getestet:"
echo "  python3 3cx_yealink_sync.py --help"
echo ""
echo "✓ Service installieren (wenn noch nicht geschehen):"
echo "  sudo cp 3cx-yealink-sync.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now 3cx-yealink-sync.service"
echo ""
echo "✓ Service-Logs überwachen:"
echo "  sudo journalctl -u 3cx-yealink-sync.service -f"
echo ""
echo "✓ Telefone konfigurieren:"
echo "  Remote Phonebook URL: http://<SERVER_IP>:8080/phonebook.csv"
echo ""
echo "✓ Unterstützung:"
echo "  Siehe: INSTALLATIONSANLEITUNG.md"
echo ""

echo "✅ Test abgeschlossen!"
