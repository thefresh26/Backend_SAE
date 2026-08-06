"""
app.py — Backend intermedio (Flask) para Vista_inmuebles_SAE.

Por qué existe este archivo:
El visor original (Vista_inmuebles_SAE, sin backend) habla DIRECTO desde el
navegador con Supabase: eso significa que el ID/URL del proyecto Supabase y
la anon key quedan visibles en el código JS que cualquiera puede leer con
F12. No es un riesgo grave (la anon key está pensada para ser pública y el
RLS protege los datos), pero si se quiere que NADA de Supabase sea visible
desde el navegador, hay que meter un backend en medio: el navegador solo le
habla a este servidor, y este servidor es el único que le habla a Supabase.

Variables de entorno necesarias (Render → Settings → Environment):
  SECRET_KEY              - clave para firmar la sesión de Flask
  SUPABASE_URL             - URL del proyecto (ej: https://xxxx.supabase.co)
  SUPABASE_ANON_KEY        - anon key (la misma que ya usa el visor actual)
  SUPABASE_SERVICE_ROLE_KEY - service_role key (bypassa RLS; usarla SOLO
                               server-side, nunca enviarla al navegador)

En local, si no defines estas variables, el servidor arranca pero el login
y las búsquedas van a fallar (no hay valores de prueba porque son
credenciales reales de una base de datos real).
"""

import os
import requests
from functools import wraps
from flask import Flask, send_from_directory, request, session, jsonify, redirect

app = Flask(__name__, static_folder="visor", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

USER_EMAILS = {
    "broker2026":    "broker2026@sae-inmuebles.app",
    "comercial2026": "comercial2026@sae-inmuebles.app",
    "SAE":           "sae@sae-inmuebles.app",
}


def obtener_ip_cliente():
    """Render pone la IP real del visitante en X-Forwarded-For (puede traer
    varias IPs separadas por coma si hay proxies de por medio; la primera
    es la del cliente). Si no viene ese header, usa la IP directa."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            return jsonify({"error": "No autenticado"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    return send_from_directory("visor", "index.html")


@app.route("/api/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    usuario = (body.get("usuario") or "").strip()
    password = body.get("password") or ""
    if not usuario or not password:
        return jsonify({"error": "Faltan credenciales"}), 400

    email = USER_EMAILS.get(usuario, usuario)

    # El login real lo sigue validando Supabase Auth (nunca guardamos ni
    # comparamos contraseñas aquí). Solo hacemos de intermediario: el
    # navegador nunca ve la URL/keys de Supabase, solo habla con nosotros.
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=10,
    )
    if r.status_code != 200:
        return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

    data = r.json()
    user = data.get("user", {})
    role = (user.get("user_metadata") or {}).get("role", "comercial")

    session["usuario"] = usuario
    session["email"] = email
    session["role"] = role

    registrar_log(email, "login", None, obtener_ip_cliente())
    return jsonify({"ok": True, "role": role})


@app.route("/api/logout", methods=["POST"])
def logout():
    detalle = (request.get_json(silent=True) or {}).get("motivo")
    if session.get("email"):
        registrar_log(session["email"], "logout" if not detalle else "logout_inactividad", detalle, obtener_ip_cliente())
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/session")
def get_session():
    if "usuario" not in session:
        return jsonify({"autenticado": False})
    return jsonify({"autenticado": True, "role": session.get("role")})


@app.route("/api/buscar")
@requires_auth
def buscar():
    folios_raw = request.args.get("folios", "")
    folios = [f.strip() for f in folios_raw.replace("/", ",").split(",") if f.strip()]
    if not folios:
        return jsonify([])

    # Usa la función RPC buscar_folios ya creada en Supabase (ver
    # 08_endurecer_sae.sql). Se llama con la service_role key porque este
    # backend SÍ es un entorno de confianza (nunca se expone al navegador).
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/buscar_folios",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
        json={"p_folios": folios},
        timeout=15,
    )
    if r.status_code != 200:
        return jsonify({"error": "Error al consultar la base de datos"}), 502

    registrar_log(session.get("email"), "busqueda", ", ".join(folios), obtener_ip_cliente())
    return jsonify(r.json())


def registrar_log(email, accion, detalle, ip=None):
    """Mejor esfuerzo: si falla el log, no interrumpe la respuesta al usuario."""
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/logs_acceso",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
            json={"usuario_email": email, "accion": accion, "detalle": detalle, "ip_address": ip},
            timeout=5,
        )
    except Exception:
        pass


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("visor", filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
