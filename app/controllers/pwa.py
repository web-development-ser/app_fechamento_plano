"""PWA: manifesto, service worker e página offline."""
from flask import Blueprint, current_app, jsonify, make_response, render_template, url_for

bp = Blueprint("pwa", __name__)

TEMA = "#1877F2"

# arquivos guardados no aparelho na instalação (abrem mesmo com conexão instável)
PRECACHE_ESTATICOS = (
    "css/app.css",
    "js/app.js",
    "js/vendor/lucide.min.js",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "icons/maskable-512.png",
    "icons/apple-touch-icon.png",
    "icons/favicon-32.png",
    "icons/icon.svg",
)


def asset(filename):
    """URL de arquivo estático com a versão da aplicação (cache longo + atualização automática)."""
    return url_for("static", filename=filename, v=current_app.config["APP_VERSION"])


@bp.route("/manifest.webmanifest")
def manifest():
    dados = {
        "id": "/",
        "name": "TEGAD – Fechamento de Plano",
        "short_name": "TEGAD",
        "description": "Atendimento de itens de reposição, programas interrompidos e consulta.",
        "lang": "pt-BR",
        "start_url": "/?origem=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": TEMA,
        "theme_color": TEMA,
        "icons": [
            {"src": asset("icons/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": asset("icons/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": asset("icons/maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": asset("icons/icon.svg"), "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
        ],
        "shortcuts": [
            {"name": "Atendimento", "url": "/atendimento/", "icons": [{"src": asset("icons/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Interrompidos", "url": "/mapeamentos/", "icons": [{"src": asset("icons/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Troca de turno", "url": "/dashboard/", "icons": [{"src": asset("icons/icon-192.png"), "sizes": "192x192"}]},
            {"name": "Consulta", "url": "/consulta/", "icons": [{"src": asset("icons/icon-192.png"), "sizes": "192x192"}]},
        ],
    }
    resp = jsonify(dados)
    resp.mimetype = "application/manifest+json"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.route("/sw.js")
def service_worker():
    corpo = render_template(
        "pwa/sw.js",
        versao=current_app.config["APP_VERSION"],
        precache=[asset(f) for f in PRECACHE_ESTATICOS] + [url_for("pwa.offline")],
        offline=url_for("pwa.offline"),
    )
    resp = make_response(corpo)
    resp.mimetype = "application/javascript"
    # o navegador deve sempre buscar a versão nova do service worker
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.route("/offline")
def offline():
    return render_template("pwa/offline.html")
