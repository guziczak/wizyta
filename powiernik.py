#!/usr/bin/env python3
"""
Powiernik - minimalny serwer API dla frontendu Wizyta.

Działa headless (bez UI), udostępnia:
- /api/health - status serwera
- /api/debug/logs - logi do debugowania
- /api/session-key - odbiera session key z rozszerzenia
- CORS dla GitHub Pages

Uruchomienie:
    python powiernik.py
    pythonw powiernik.py  # bez okna konsoli
"""

import os
import sys
import json
import ssl
import ipaddress
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, Response, make_response, send_file, send_from_directory

# ---------------------------------------------------------------------------
# SSL Certificate Generation
# ---------------------------------------------------------------------------
def generate_self_signed_cert(cert_path: Path, key_path: Path):
    """Generuje self-signed certyfikat SSL dla localhost."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime as dt

        # Generuj klucz prywatny
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Dane certyfikatu
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "PL"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Wizyta Powiernik"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        # Buduj certyfikat
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.utcnow())
            .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256(), default_backend())
        )

        # Zapisz klucz
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # Zapisz certyfikat
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"Błąd generowania certyfikatu: {e}")
        return False

def ensure_ssl_cert():
    """Upewnia się że certyfikat SSL istnieje."""
    cert_dir = BASE_DIR / "ssl"
    cert_dir.mkdir(exist_ok=True)
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    log("info", "Generuję certyfikat SSL dla HTTPS...")
    if generate_self_signed_cert(cert_path, key_path):
        log("info", "Certyfikat SSL wygenerowany.")
        return cert_path, key_path
    else:
        log("warn", "Nie można wygenerować certyfikatu. Używam HTTP.")
        return None, None

# ---------------------------------------------------------------------------
# Ścieżki
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
STDOUT_LOG_FILE = LOG_DIR / "stdout.log"
APP_LOG_FILE = LOG_DIR / "app.log"
CONFIG_FILE = BASE_DIR / "config.json"

LOG_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Prosty logger
# ---------------------------------------------------------------------------
def log(level: str, msg: str):
    """Loguje do pliku i stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} [{level.upper()}] {msg}"
    print(line, flush=True)
    try:
        with open(APP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Config Manager (uproszczony)
# ---------------------------------------------------------------------------
class ConfigManager:
    """Prosty manager konfiguracji JSON."""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path
        self._data = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log("error", f"Nie można zapisać config: {e}")

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def read_tail(filepath: Path, lines: int = 200) -> list[str]:
    """Czyta ostatnie N linii z pliku."""
    if not filepath.exists():
        return []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            return [line.rstrip() for line in all_lines[-lines:]]
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.before_request
def handle_preflight():
    """Obsługuje preflight requests dla Private Network Access."""
    if request.method == 'OPTIONS':
        response = make_response()
        origin = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        # Kluczowe dla Private Network Access
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response, 204

@app.after_request
def add_cors_headers(response):
    """Dodaje nagłówki CORS i Private Network Access do wszystkich odpowiedzi."""
    origin = request.headers.get("Origin", "")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# ---------------------------------------------------------------------------
# Frontend routes
# ---------------------------------------------------------------------------
@app.route('/')
def serve_frontend():
    """Serwuje główną stronę aplikacji."""
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return send_file(index_path, mimetype='text/html')
    return "Frontend nie znaleziony. Uruchom ponownie instalator.", 404

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serwuje pliki statyczne (CSS, JS, obrazki)."""
    assets_dir = BASE_DIR / "assets"
    if assets_dir.exists():
        return send_from_directory(assets_dir, filename)
    return "Asset nie znaleziony", 404

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@app.route('/api/health', methods=['GET', 'OPTIONS'])
def healthcheck():
    """Status serwera dla frontendu."""
    if request.method == 'OPTIONS':
        return '', 204

    cfg = ConfigManager()
    return jsonify({
        "ok": True,
        "message": "Powiernik odpowiada",
        "backend": cfg.get("transcriber_backend", "openvino_whisper"),
        "model": cfg.get("transcriber_model", "small"),
        "device": cfg.get("selected_device", "auto"),
        "port": PORT,
        "timestamp": datetime.now().isoformat(),
    })

@app.route('/api/debug/logs', methods=['GET', 'OPTIONS'])
def debug_logs():
    """Zwraca ostatnie linie logów."""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        tail = int(request.args.get("tail", "200"))
    except ValueError:
        tail = 200
    tail = max(10, min(tail, 2000))

    app_lines = read_tail(APP_LOG_FILE, tail)
    stdout_lines = read_tail(STDOUT_LOG_FILE, tail)

    return jsonify({
        "lines": app_lines,
        "stdout_lines": stdout_lines,
        "timestamp": datetime.now().isoformat(),
    })

@app.route('/api/session-key', methods=['POST', 'OPTIONS'])
def receive_session_key():
    """Odbiera session key z rozszerzenia przeglądarki."""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        session_key = data.get('sessionKey') if data else None
        if session_key:
            cfg = ConfigManager()
            cfg.set('session_key', session_key)
            log("info", "Session key otrzymany z rozszerzenia")
            return jsonify({'success': True, 'message': 'Session key zapisany'})
        return jsonify({'success': False, 'error': 'Brak sessionKey'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
PORT = 8089

def main():
    log("info", "========================================")
    log("info", "  POWIERNIK - Backend dla Wizyta")
    log("info", "========================================")
    log("info", f"Port: {PORT}")

    # Sprawdź/generuj certyfikat SSL
    cert_path, key_path = ensure_ssl_cert()
    use_https = cert_path is not None and key_path is not None

    protocol = "https" if use_https else "http"
    log("info", f"Frontend: {protocol}://127.0.0.1:{PORT}/")
    log("info", "")

    # Sprawdź czy port jest wolny
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', PORT))
    sock.close()
    if result == 0:
        log("warn", f"Port {PORT} jest już zajęty!")
        log("info", "Może inna instancja Powiernika już działa?")

    # Uruchom serwer
    log("info", f"Uruchamiam serwer na http://127.0.0.1:{PORT}")
    log("info", "Naciśnij Ctrl+C aby zatrzymać.")

    # Wyłącz debug output Flaska
    import logging
    werkzeug_log = logging.getLogger('werkzeug')
    werkzeug_log.setLevel(logging.WARNING)

    try:
        if use_https:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(str(cert_path), str(key_path))
            log("info", "Uruchamiam serwer HTTPS...")
            log("info", "UWAGA: Przy pierwszym połączeniu zaakceptuj certyfikat w przeglądarce!")
            app.run(
                host='0.0.0.0',
                port=PORT,
                debug=False,
                threaded=True,
                use_reloader=False,
                ssl_context=ssl_context
            )
        else:
            log("info", "Uruchamiam serwer HTTP...")
            app.run(
                host='0.0.0.0',
                port=PORT,
                debug=False,
                threaded=True,
                use_reloader=False
            )
    except KeyboardInterrupt:
        log("info", "Zatrzymano przez użytkownika.")
    except Exception as e:
        log("error", f"Błąd serwera: {e}")

if __name__ == "__main__":
    main()
