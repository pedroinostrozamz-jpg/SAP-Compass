import streamlit as st
import anthropic
import requests
import json
import re
from datetime import datetime

# =============================
# CONFIGURACIÓN STREAMLIT
# =============================
st.set_page_config(
    page_title="SAP Compass Suite — Corporate Finder",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =============================
# KEYS DESDE STREAMLIT SECRETS
# =============================
ANTHROPIC_API_KEY = st.secrets["ANTHROPIC_API_KEY"]
SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
MODELO = "claude-sonnet-4-6"
PAISES_DISPONIBLES = ["Argentina", "Chile", "Perú", "Colombia"]

# Logo SAP embebido como URL pública oficial (no requiere archivo local)
SAP_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/5/59/SAP_2011_logo.svg"

try:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
except Exception as e:
    st.error("Error inicializando Claude. Revisa tu API Key en Streamlit Secrets.")
    st.stop()


# =============================
# FUNCIÓN: BUSCAR IMÁGENES (Logo + Fotos empresa)
# =============================
def buscar_imagenes_empresa(empresa, pais):
    """Busca logo y fotos de la empresa usando SerpAPI Google Images."""
    resultados = {"logo": None, "fotos": []}

    # Buscar logo
    params_logo = {
        "engine": "google_images",
        "q": f"{empresa} logo oficial",
        "hl": "es",
        "gl": "us",
        "num": "5",
        "api_key": SERPAPI_KEY
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params_logo, timeout=10)
        if r.status_code == 200:
            data = r.json()
            images = data.get("images_results", [])
            for img in images[:5]:
                url = img.get("original", "")
                # Preferir imágenes pequeñas/cuadradas típicas de logos
                if url and any(ext in url.lower() for ext in [".png", ".jpg", ".svg", ".webp"]):
                    resultados["logo"] = url
                    break
    except Exception:
        pass

    # Buscar fotos de la empresa (sede, instalaciones)
    params_fotos = {
        "engine": "google_images",
        "q": f"{empresa} {pais} sede oficinas instalaciones",
        "hl": "es",
        "gl": "us",
        "num": "10",
        "api_key": SERPAPI_KEY
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params_fotos, timeout=10)
        if r.status_code == 200:
            data = r.json()
            images = data.get("images_results", [])
            fotos = []
            for img in images[:8]:
                url = img.get("original", "")
                thumbnail = img.get("thumbnail", "")
                titulo = img.get("title", "")
                if url and thumbnail:
                    fotos.append({"url": url, "thumbnail": thumbnail, "titulo": titulo})
            resultados["fotos"] = fotos[:4]  # máximo 4 fotos
    except Exception:
        pass

    return resultados


# =============================
# FUNCIÓN: MERCANTIL.COM (solo Chile)
# =============================
def buscar_mercantil(empresa, pais):
    if pais.strip().lower() not in ["chile"]:
        return ""
    query = f"{empresa} Chile mercantil"
    params = {
        "engine": "google",
        "q": query,
        "hl": "es",
        "gl": "cl",
        "api_key": SERPAPI_KEY
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=10)
        if r.status_code != 200:
            return ""
        data = r.json()
        for item in data.get("organic_results", []):
            link = item.get("link", "")
            if "mercantil.com" in link.lower():
                return link
    except Exception:
        return ""
    return ""


# =============================
# FUNCIÓN: BUSCAR LINKEDIN (SerpAPI)
# =============================
def buscar_linkedin_ejecutivos(empresa, pais):
    query = f'site:linkedin.com/in "{empresa}" {pais} CEO CFO gerente director'
    params = {
        "engine": "google",
        "q": query,
        "hl": "es",
        "num": "10",
        "api_key": SERPAPI_KEY
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        ejecutivos = []
        for item in data.get("organic_results", []):
            link = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            if "linkedin.com/in/" not in link.lower():
                continue
            texto_completo = (title + " " + snippet).lower()
            palabras_empresa = empresa.lower().split()[:2]
            menciona_empresa = any(p in texto_completo for p in palabras_empresa)
            if not menciona_empresa:
                continue
            nombre = title.split(" - ")[0].strip() if " - " in title else title
            cargo = ""
            if " - " in title:
                partes = title.split(" - ")
                cargo = partes[1].strip() if len(partes) > 1 else ""
            ejecutivos.append({"nombre": nombre, "cargo": cargo, "link": link, "snippet": snippet})
        return ejecutivos[:5]
    except Exception:
        return []


# =============================
# FUNCIÓN: CONSULTAR CLAUDE
# =============================
def consultar_claude(empresa, pais):
    prompt = f"""Eres un analista corporativo SAP. Busca en internet información sobre **{empresa}** en **{pais}** y devuelve SOLO este JSON sin texto adicional:

{{
  "nombre_empresa": "{empresa}",
  "pais": "{pais}",
  "sitio_web": "URL oficial",
  "rubro": "Industria o sector",
  "descripcion": "Descripción breve (2 oraciones)",
  "mision": "Misión oficial",
  "vision": "Visión oficial",
  "fundacion": "Año",
  "empleados": "Cantidad aproximada",
  "facturacion_anual": "Ingresos anuales",
  "presencia_geografica": "Países donde opera",
  "direccion_sede": "Dirección completa de la sede principal (calle, ciudad, país)",
  "importaciones_exportaciones": "Comercio exterior",
  "tecnologia_it": "Sistemas IT conocidos",
  "soluciones_sap": "Soluciones SAP actuales",
  "oportunidades_sap": "Oportunidades SAP identificadas",
  "noticias": [
    {{"titulo": "","resumen": "","fecha": "","fuente": ""}}
  ],
  "ejecutivos_conocidos": [
    {{"nombre": "","cargo": ""}}
  ]
}}

Reglas: máximo 3 noticias, máximo 5 ejecutivos, solo ejecutivos de {empresa}, si no hay certeza escribe "Información no disponible".
"""
    try:
        message = client.messages.create(
            model=MODELO,
            max_tokens=2000,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3
            }],
            messages=[{"role": "user", "content": prompt}]
        )
        raw = ""
        for block in message.content:
            if hasattr(block, "type") and block.type == "text":
                raw = block.text.strip()
                break
        if not raw:
            st.error("Claude no devolvió texto. Intenta nuevamente.")
            return None
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        return json.loads(raw)
    except json.JSONDecodeError:
        st.error("Claude no devolvió un JSON válido. Intenta nuevamente.")
        return None
    except Exception as e:
        st.error(f"Error consultando Claude: {e}")
        return None


# =============================
# CSS PERSONALIZADO
# =============================
def inyectar_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --sap-blue: #0070F2;
        --sap-dark: #003366;
        --sap-mid: #0056CC;
        --text-primary: #1A2B42;
        --text-muted: #5A6A7A;
        --text-hint: #8A9BAB;
        --surface: #FFFFFF;
        --surface-2: #F4F6F9;
        --border: #D0DCE8;
        --acento: #F5A623;
        --exito: #10B981;
        --radius: 10px;
        --radius-lg: 16px;
    }

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
    }

    .stApp {
        background: var(--surface-2) !important;
    }

    /* ── HERO HEADER ── */
    .sap-hero {
        background: linear-gradient(135deg, #003366 0%, #0056CC 55%, #0070F2 100%);
        border-radius: var(--radius-lg);
        padding: 36px 40px;
        position: relative;
        overflow: hidden;
        margin-bottom: 28px;
    }
    .sap-hero::before {
        content: '';
        position: absolute;
        top: -80px; right: -60px;
        width: 320px; height: 320px;
        background: rgba(255,255,255,0.05);
        border-radius: 50%;
    }
    .sap-hero::after {
        content: '';
        position: absolute;
        bottom: -100px; right: 80px;
        width: 200px; height: 200px;
        background: rgba(255,255,255,0.04);
        border-radius: 50%;
    }
    .hero-top {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 20px;
    }
    .hero-sap-logo {
        height: 36px;
        width: auto;
        filter: brightness(0) invert(1);
        flex-shrink: 0;
    }
    .hero-divider {
        width: 1px;
        height: 28px;
        background: rgba(255,255,255,0.25);
        flex-shrink: 0;
    }
    .hero-tool-name {
        font-size: 13px;
        font-weight: 600;
        color: rgba(255,255,255,0.9);
        letter-spacing: 0.6px;
        text-transform: uppercase;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 700;
        color: #FFFFFF;
        line-height: 1.15;
        margin-bottom: 8px;
        letter-spacing: -0.5px;
        position: relative;
        z-index: 1;
    }
    .hero-title span { color: #7EC8F7; }
    .hero-subtitle {
        font-size: 14px;
        color: rgba(255,255,255,0.65);
        font-weight: 400;
        position: relative;
        z-index: 1;
    }
    .hero-subtitle strong { color: rgba(255,255,255,0.9); font-weight: 500; }
    .hero-countries {
        display: flex;
        gap: 8px;
        margin-top: 18px;
        flex-wrap: wrap;
        position: relative;
        z-index: 1;
    }
    .country-tag {
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
        color: rgba(255,255,255,0.8);
        font-weight: 400;
    }

    /* ── FORM CARD ── */
    .form-card {
        background: var(--surface);
        border-radius: var(--radius-lg);
        border: 1px solid var(--border);
        padding: 24px 28px;
        box-shadow: 0 2px 12px rgba(0,48,102,0.06);
        margin-bottom: 28px;
    }
    .form-section-label {
        font-size: 11px;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .form-section-label::before {
        content: '';
        display: block;
        width: 3px;
        height: 14px;
        background: var(--sap-blue);
        border-radius: 2px;
    }

    /* ── EMPRESA HEADER ── */
    .empresa-header {
        background: linear-gradient(135deg, #003366 0%, #0D3B6E 100%);
        border-radius: var(--radius-lg);
        padding: 28px 32px;
        color: white;
        margin-bottom: 20px;
        display: flex;
        gap: 24px;
        align-items: flex-start;
    }
    .empresa-logo-container {
        width: 80px;
        height: 80px;
        background: white;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        overflow: hidden;
        border: 2px solid rgba(255,255,255,0.2);
    }
    .empresa-logo-container img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        padding: 8px;
    }
    .empresa-logo-placeholder {
        width: 80px;
        height: 80px;
        background: rgba(255,255,255,0.12);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.8rem;
        flex-shrink: 0;
        border: 2px solid rgba(255,255,255,0.15);
    }
    .empresa-info { flex: 1; }
    .empresa-rubro {
        color: var(--acento);
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    .empresa-nombre {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0 0 6px 0;
        letter-spacing: -0.5px;
    }
    .empresa-desc {
        color: rgba(255,255,255,0.7);
        font-size: 0.87rem;
        line-height: 1.5;
        margin-bottom: 14px;
    }
    .empresa-meta {
        display: flex;
        gap: 24px;
        flex-wrap: wrap;
    }
    .empresa-meta-item { display: flex; flex-direction: column; gap: 2px; }
    .empresa-meta-label {
        font-size: 0.68rem;
        color: rgba(255,255,255,0.55);
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .empresa-meta-value {
        font-size: 0.9rem;
        font-weight: 600;
        color: white;
    }
    .empresa-meta-value a { color: var(--acento); text-decoration: none; }

    /* ── KPI CARDS ── */
    .kpi-card {
        background: white;
        border-radius: var(--radius);
        padding: 18px;
        border: 1px solid var(--border);
        text-align: center;
        box-shadow: 0 1px 6px rgba(0,0,0,0.04);
    }
    .kpi-icono { font-size: 1.6rem; margin-bottom: 6px; }
    .kpi-valor {
        font-size: 1rem;
        font-weight: 700;
        color: var(--sap-dark);
        line-height: 1.3;
    }
    .kpi-label {
        font-size: 0.68rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-top: 4px;
    }

    /* ── CARDS ── */
    .card {
        background: var(--surface);
        border-radius: var(--radius-lg);
        padding: 22px 24px;
        margin-bottom: 18px;
        border: 1px solid var(--border);
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    }
    .card-titulo {
        font-size: 11px;
        font-weight: 600;
        color: var(--sap-blue);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .card-titulo::after {
        content: '';
        flex: 1;
        height: 1px;
        background: var(--border);
    }

    /* ── GALERÍA DE FOTOS ── */
    .galeria-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
    }
    .galeria-item {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid var(--border);
        aspect-ratio: 16/9;
        background: var(--surface-2);
    }
    .galeria-item img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }

    /* ── MAPA ── */
    .mapa-container {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid var(--border);
    }
    .mapa-container iframe {
        display: block;
        border: none;
    }

    /* ── NOTICIAS ── */
    .noticia-item {
        border-left: 3px solid var(--sap-blue);
        padding: 12px 16px;
        margin-bottom: 12px;
        background: #F0F6FF;
        border-radius: 0 8px 8px 0;
    }
    .noticia-titulo {
        font-weight: 600;
        color: var(--text-primary);
        font-size: 0.9rem;
        margin-bottom: 4px;
    }
    .noticia-resumen {
        color: var(--text-muted);
        font-size: 0.82rem;
        line-height: 1.5;
    }
    .noticia-meta {
        font-size: 0.7rem;
        color: var(--sap-blue);
        margin-top: 6px;
        font-family: 'IBM Plex Mono', monospace;
    }

    /* ── EJECUTIVOS ── */
    .ejecutivo-avatar {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, var(--sap-dark), var(--sap-blue));
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 0.9rem;
        flex-shrink: 0;
    }
    .ejecutivo-nombre {
        font-weight: 600;
        color: var(--text-primary);
        font-size: 0.88rem;
    }
    .ejecutivo-cargo {
        color: var(--text-muted);
        font-size: 0.76rem;
        margin-top: 1px;
    }
    .ejecutivo-linkedin {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #0A66C2;
        color: white;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        text-decoration: none;
        flex-shrink: 0;
    }

    /* ── MERCANTIL ── */
    .mercantil-link {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #F0FDF4;
        border: 1px solid #BBF7D0;
        color: #15803D;
        padding: 10px 16px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.88rem;
        text-decoration: none;
        width: 100%;
    }

    /* ── NO DISPONIBLE ── */
    .no-disponible {
        color: var(--text-hint);
        font-style: italic;
        font-size: 0.85rem;
    }

    /* ── FOOTER ── */
    .footer-info {
        text-align: center;
        color: var(--text-hint);
        font-size: 0.75rem;
        padding: 20px;
        margin-top: 8px;
        font-family: 'IBM Plex Mono', monospace;
    }

    /* Ocultar elementos Streamlit */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }

    /* Botón primario con estilo SAP */
    .stButton > button[kind="primary"] {
        background: var(--sap-blue) !important;
        border-color: var(--sap-blue) !important;
        font-family: 'IBM Plex Sans', sans-serif !important;
        font-weight: 600 !important;
        border-radius: var(--radius) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #005FD6 !important;
        border-color: #005FD6 !important;
    }
    </style>
    """, unsafe_allow_html=True)


# =============================
# HELPERS
# =============================
def es_disponible(valor):
    if not valor:
        return False
    return "no disponible" not in str(valor).lower() and str(valor).strip() != ""

def render_valor(valor, fallback="Información no disponible"):
    if es_disponible(valor):
        return str(valor)
    return f'<span class="no-disponible">{fallback}</span>'

def iniciales(nombre):
    partes = nombre.split()
    if len(partes) >= 2:
        return f"{partes[0][0]}{partes[1][0]}".upper()
    return nombre[:2].upper()

def generar_url_maps(direccion, empresa, pais):
    """Genera URL de Google Maps embed sin API key."""
    query = requests.utils.quote(f"{empresa}, {direccion or pais}")
    return f"https://maps.google.com/maps?q={query}&output=embed&z=15"


# =============================
# RENDERIZADO DEL INFORME
# =============================
def renderizar_informe(datos, linkedin_ejecutivos, mercantil_link, imagenes):

    logo_url = imagenes.get("logo")
    fotos = imagenes.get("fotos", [])

    # ── Header empresa ──────────────────────────────────────────────
    if logo_url:
        logo_html = f'<div class="empresa-logo-container"><img src="{logo_url}" alt="Logo {datos.get("nombre_empresa","")}" onerror="this.parentElement.innerHTML=\'🏢\'"></div>'
    else:
        logo_html = '<div class="empresa-logo-placeholder">🏢</div>'

    st.markdown(f"""
    <div class="empresa-header">
        {logo_html}
        <div class="empresa-info">
            <div class="empresa-rubro">{datos.get('rubro', 'Empresa')}</div>
            <div class="empresa-nombre">{datos.get('nombre_empresa', '')}</div>
            <div class="empresa-desc">{datos.get('descripcion', '')}</div>
            <div class="empresa-meta">
                <div class="empresa-meta-item">
                    <span class="empresa-meta-label">País</span>
                    <span class="empresa-meta-value">{datos.get('pais', '—')}</span>
                </div>
                <div class="empresa-meta-item">
                    <span class="empresa-meta-label">Fundación</span>
                    <span class="empresa-meta-value">{datos.get('fundacion', '—')}</span>
                </div>
                <div class="empresa-meta-item">
                    <span class="empresa-meta-label">Sitio Web</span>
                    <span class="empresa-meta-value">
                        <a href="{datos.get('sitio_web', '#')}" target="_blank">{datos.get('sitio_web', '—')}</a>
                    </span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4, gap="small")
    for col, icono, valor, label in [
        (k1, "👥", datos.get('empleados', '—'), "Empleados"),
        (k2, "💰", datos.get('facturacion_anual', '—'), "Facturación Anual"),
        (k3, "🌎", datos.get('presencia_geografica', '—'), "Presencia"),
        (k4, "🚢", datos.get('importaciones_exportaciones', '—'), "Comercio Exterior"),
    ]:
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-icono">{icono}</div>
                <div class="kpi-valor">{valor}</div>
                <div class="kpi-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Columnas principales ─────────────────────────────────────────
    col_izq, col_der = st.columns([3, 2], gap="medium")

    with col_izq:

        # Misión y Visión
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo">🎯 Misión & Visión</div>
            <p style="font-size:0.88rem;color:#374151;margin-bottom:10px;">
                <strong>Misión:</strong> {render_valor(datos.get('mision'))}
            </p>
            <p style="font-size:0.88rem;color:#374151;margin:0;">
                <strong>Visión:</strong> {render_valor(datos.get('vision'))}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Tecnología IT
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo">💻 Tecnología & IT</div>
            <p style="font-size:0.88rem;color:#374151;margin:0;">
                {render_valor(datos.get('tecnologia_it'))}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # SAP Intelligence
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo">⚡ SAP Intelligence</div>
            <p style="font-size:0.75rem;font-weight:600;color:#B45309;margin-bottom:6px;">SOLUCIONES ACTUALES</p>
            <p style="font-size:0.88rem;color:#374151;margin-bottom:14px;">
                {render_valor(datos.get('soluciones_sap'))}
            </p>
            <p style="font-size:0.75rem;font-weight:600;color:#065F46;margin-bottom:6px;">OPORTUNIDADES IDENTIFICADAS</p>
            <p style="font-size:0.88rem;color:#374151;margin:0;">
                {render_valor(datos.get('oportunidades_sap'))}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Noticias
        st.markdown('<div class="card"><div class="card-titulo">📰 Noticias Relevantes</div>', unsafe_allow_html=True)
        noticias = datos.get('noticias', [])
        if noticias:
            for n in noticias:
                titulo = n.get('titulo', '')
                if titulo and "no disponible" not in titulo.lower():
                    st.markdown(f"""
                    <div class="noticia-item">
                        <div class="noticia-titulo">{titulo}</div>
                        <div class="noticia-resumen">{n.get('resumen','')}</div>
                        <div class="noticia-meta">📅 {n.get('fecha','')} &nbsp;·&nbsp; 📌 {n.get('fuente','')}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown('<span class="no-disponible">No se encontraron noticias recientes.</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Galería de fotos
        if fotos:
            items_html = ""
            for foto in fotos:
                items_html += f"""
                <div class="galeria-item">
                    <img src="{foto['thumbnail']}" alt="{foto['titulo']}"
                         onerror="this.parentElement.style.display='none'">
                </div>"""
            st.markdown(f"""
            <div class="card">
                <div class="card-titulo">📸 Galería de la Empresa</div>
                <div class="galeria-grid">{items_html}</div>
            </div>
            """, unsafe_allow_html=True)

    with col_der:

        # Directorio Ejecutivo
        st.markdown('<div class="card"><div class="card-titulo">👤 Directorio Ejecutivo</div>', unsafe_allow_html=True)

        ejecutivos_claude = datos.get('ejecutivos_conocidos', [])
        linkedin_map = {}
        for li in linkedin_ejecutivos:
            linkedin_map[li.get('nombre', '').lower()] = li

        def buscar_linkedin_match(nombre):
            for key, val in linkedin_map.items():
                if nombre.split()[0].lower() in key or (key.split()[0] in nombre.lower()):
                    return val
            return None

        ejecutivos_mostrados = set()

        for ej in ejecutivos_claude:
            nombre = ej.get('nombre', '').strip()
            cargo = ej.get('cargo', '').strip()
            if not nombre or "no disponible" in nombre.lower():
                continue
            ejecutivos_mostrados.add(nombre.split()[0].lower())
            li_match = buscar_linkedin_match(nombre)

            col_av, col_info = st.columns([1, 4])
            with col_av:
                st.markdown(f'<div class="ejecutivo-avatar" style="margin-top:4px;">{iniciales(nombre)}</div>', unsafe_allow_html=True)
            with col_info:
                st.markdown(f'<div class="ejecutivo-nombre">{nombre}</div><div class="ejecutivo-cargo">{cargo}</div>', unsafe_allow_html=True)
                if li_match:
                    st.markdown(f'<a class="ejecutivo-linkedin" href="{li_match["link"]}" target="_blank">in LinkedIn</a>', unsafe_allow_html=True)
            st.markdown("<hr style='margin:6px 0;border-color:#E2E8F0;'>", unsafe_allow_html=True)

        for li in linkedin_ejecutivos:
            nombre_li = li.get('nombre', '').strip()
            if not nombre_li:
                continue
            ya = any(nombre_li.split()[0].lower() in inc for inc in ejecutivos_mostrados)
            if ya:
                continue
            col_av, col_info = st.columns([1, 4])
            with col_av:
                st.markdown(f'<div class="ejecutivo-avatar" style="margin-top:4px;">{iniciales(nombre_li)}</div>', unsafe_allow_html=True)
            with col_info:
                st.markdown(f'<div class="ejecutivo-nombre">{nombre_li}</div><div class="ejecutivo-cargo">{li.get("cargo","")}</div>', unsafe_allow_html=True)
                st.markdown(f'<a class="ejecutivo-linkedin" href="{li.get("link","#")}" target="_blank">in LinkedIn</a>', unsafe_allow_html=True)
            st.markdown("<hr style='margin:6px 0;border-color:#E2E8F0;'>", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # Contexto Comercial
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo">🌐 Contexto Comercial</div>
            <p style="font-size:0.75rem;font-weight:600;color:#374151;margin-bottom:4px;">PRESENCIA GEOGRÁFICA</p>
            <p style="font-size:0.85rem;color:#6B7280;margin-bottom:12px;">{render_valor(datos.get('presencia_geografica'))}</p>
            <p style="font-size:0.75rem;font-weight:600;color:#374151;margin-bottom:4px;">COMERCIO EXTERIOR</p>
            <p style="font-size:0.85rem;color:#6B7280;margin:0;">{render_valor(datos.get('importaciones_exportaciones'))}</p>
        </div>
        """, unsafe_allow_html=True)

        # Mapa Google Maps
        direccion = datos.get('direccion_sede', '')
        empresa_nombre = datos.get('nombre_empresa', '')
        pais_nombre = datos.get('pais', '')
        maps_url = generar_url_maps(direccion, empresa_nombre, pais_nombre)

        direccion_display = direccion if es_disponible(direccion) else f"{empresa_nombre}, {pais_nombre}"

        st.markdown(f"""
        <div class="card">
            <div class="card-titulo">📍 Ubicación</div>
            <p style="font-size:0.8rem;color:var(--text-muted);margin-bottom:10px;">{direccion_display}</p>
            <div class="mapa-container">
                <iframe
                    src="{maps_url}"
                    width="100%"
                    height="220"
                    loading="lazy"
                    referrerpolicy="no-referrer-when-downgrade">
                </iframe>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Mercantil (solo Chile)
        if mercantil_link:
            st.markdown(f"""
            <div class="card">
                <div class="card-titulo">📋 Mercantil.com</div>
                <a class="mercantil-link" href="{mercantil_link}" target="_blank">
                    🔗 Ver ficha en Mercantil.com
                </a>
            </div>
            """, unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
    <div class="footer-info">
        Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")} &nbsp;·&nbsp;
        SAP Compass Suite — Corporate Intelligence Finder &nbsp;·&nbsp; Powered by Claude Sonnet 4.6
    </div>
    """, unsafe_allow_html=True)


# =============================
# INTERFAZ PRINCIPAL
# =============================
inyectar_css()

# Header principal
st.markdown(f"""
<div class="sap-hero">
    <div class="hero-top">
        <img class="hero-sap-logo" src="{SAP_LOGO_URL}" alt="SAP Logo" />
        <div class="hero-divider"></div>
        <span class="hero-tool-name">SAP Compass Suite</span>
    </div>
    <h1 class="hero-title">Corporate <span>Intelligence</span> Finder</h1>
    <p class="hero-subtitle">Plataforma de <strong>perfilamiento ejecutivo</strong> y análisis de cuentas estratégicas</p>
    <div class="hero-countries">
        <div class="country-tag">Argentina</div>
        <div class="country-tag">Chile</div>
        <div class="country-tag">Perú</div>
        <div class="country-tag">Colombia</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Formulario
st.markdown('<div class="form-card">', unsafe_allow_html=True)
st.markdown('<div class="form-section-label">Generar perfil corporativo</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([3, 2, 1], gap="medium")
with col1:
    empresa = st.text_input("Nombre de la empresa", placeholder="Ej: Minera Veta Dorada", label_visibility="collapsed")
with col2:
    pais = st.selectbox("País", PAISES_DISPONIBLES, label_visibility="collapsed")
with col3:
    buscar = st.button("Generar Perfil →", use_container_width=True, type="primary")

st.markdown('</div>', unsafe_allow_html=True)

# Ejecución
if buscar:
    if not empresa.strip():
        st.error("Por favor ingresa el nombre de una empresa.")
        st.stop()

    with st.status("Generando perfil corporativo...", expanded=True) as status:
        st.write("Consultando Claude para información corporativa...")
        datos = consultar_claude(empresa.strip(), pais)

        if datos is None:
            status.update(label="Error al generar el perfil.", state="error")
            st.stop()

        st.write("Buscando logo e imágenes de la empresa...")
        imagenes = buscar_imagenes_empresa(empresa.strip(), pais)

        st.write("Buscando ejecutivos en LinkedIn...")
        linkedin_ejecutivos = buscar_linkedin_ejecutivos(empresa.strip(), pais)

        mercantil_link = ""
        if pais.lower() == "chile":
            st.write("Buscando en Mercantil.com...")
            mercantil_link = buscar_mercantil(empresa.strip(), pais)

        status.update(label="Perfil generado exitosamente.", state="complete")

    st.success(f"Perfil de **{empresa}** en **{pais}** generado correctamente.")
    renderizar_informe(datos, linkedin_ejecutivos, mercantil_link, imagenes)
