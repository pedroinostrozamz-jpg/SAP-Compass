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
    page_title="SAP Compass — Corporate Finder",
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

# Iniciar cliente Anthropic
try:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
except Exception as e:
    st.error(" Error inicializando Claude. Revisa tu API Key en Streamlit Secrets.")
    st.stop()


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
    query = f"site:linkedin.com/in {empresa} {pais} CEO CFO gerente director ejecutivo"
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

            if "linkedin.com/in/" in link.lower():
                # Extraer nombre y cargo del título
                nombre = title.split(" - ")[0].strip() if " - " in title else title
                cargo = ""
                if " - " in title:
                    partes = title.split(" - ")
                    cargo = partes[1].strip() if len(partes) > 1 else ""

                ejecutivos.append({
                    "nombre": nombre,
                    "cargo": cargo,
                    "link": link,
                    "snippet": snippet
                })

        return ejecutivos[:6]  # máximo 6 ejecutivos
    except Exception:
        return []


# =============================
# FUNCIÓN: CONSULTAR CLAUDE
# =============================
def consultar_claude(empresa, pais):
    prompt = f"""Eres un analista corporativo especializado en inteligencia de cuentas para ejecutivos comerciales de SAP.

Tu tarea es generar un perfil ejecutivo completo de la empresa **{empresa}** en **{pais}**.

INSTRUCCIONES IMPORTANTES:
- Responde ÚNICAMENTE en formato JSON válido, sin texto adicional antes ni después.
- Si no tienes información confiable sobre algún campo, escribe exactamente: "Información no disponible"
- NO inventes ni estimes datos financieros o de personal. Solo incluye lo que conozcas con certeza.
- Sé específico y orientado a oportunidades de negocio SAP.

Devuelve el siguiente JSON:

{{
  "nombre_empresa": "{empresa}",
  "pais": "{pais}",
  "sitio_web": "URL oficial de la empresa",
  "rubro": "Industria o sector al que pertenece",
  "descripcion": "Descripción breve de a qué se dedica la empresa (2-3 oraciones)",
  "mision": "Misión corporativa oficial o propósito declarado",
  "vision": "Visión corporativa oficial o aspiración a largo plazo",
  "fundacion": "Año de fundación",
  "empleados": "Cantidad aproximada de empleados (ej: 500-1000, o número exacto si se conoce)",
  "facturacion_anual": "Facturación o ingresos anuales aproximados en USD o moneda local",
  "presencia_geografica": "Países o regiones donde opera",
  "importaciones_exportaciones": "Si importa o exporta, qué productos/servicios",
  "tecnologia_it": "Sistemas de IT conocidos o mencionados públicamente (ERP, CRM, etc.)",
  "soluciones_sap": "Soluciones SAP que ya usan, si se sabe",
  "oportunidades_sap": "Áreas donde SAP podría agregar valor basado en el perfil de la empresa",
  "noticias": [
    {{
      "titulo": "Título de la noticia",
      "resumen": "Resumen breve",
      "fecha": "Fecha aproximada o año",
      "fuente": "Medio o fuente"
    }}
  ],
  "ejecutivos_conocidos": [
    {{
      "nombre": "Nombre completo",
      "cargo": "Cargo"
    }}
  ]
}}

Genera máximo 3 noticias relevantes de los últimos 12-18 meses.
Genera máximo 5 ejecutivos conocidos.
"""

    try:
        message = client.messages.create(
            model=MODELO,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()

        # Limpiar posibles bloques markdown
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)

        return json.loads(raw)

    except json.JSONDecodeError:
        st.error(" Claude no devolvió un JSON válido. Intenta nuevamente.")
        return None
    except Exception as e:
        st.error(f" Error consultando Claude: {e}")
        return None


# =============================
# CSS PERSONALIZADO
# =============================
def inyectar_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=DM+Mono:wght@400;500&display=swap');

    :root {
        --azul: #0A4B8C;
        --azul-claro: #1A73C8;
        --acento: #F0A500;
        --fondo: #F0F2F5;
        --card: #FFFFFF;
        --texto: #1A1A2E;
        --suave: #6B7280;
        --borde: #E2E8F0;
        --exito: #10B981;
        --advertencia: #F59E0B;
    }

    html, body, [class*="css"] {
        font-family: 'Sora', sans-serif;
    }

    .stApp {
        background: var(--fondo);
    }

    /* HEADER */
    .header-principal {
        background: linear-gradient(135deg, var(--azul) 0%, var(--azul-claro) 100%);
        padding: 32px 40px;
        border-radius: 16px;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
    }
    .header-principal::before {
        content: '';
        position: absolute;
        top: -40px; right: -40px;
        width: 200px; height: 200px;
        background: rgba(255,255,255,0.05);
        border-radius: 50%;
    }
    .header-principal::after {
        content: '';
        position: absolute;
        bottom: -60px; left: 30%;
        width: 300px; height: 300px;
        background: rgba(240,165,0,0.08);
        border-radius: 50%;
    }
    .header-titulo {
        font-size: 2.2rem;
        font-weight: 700;
        color: white;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-subtitulo {
        color: rgba(255,255,255,0.75);
        font-size: 0.95rem;
        margin-top: 4px;
        font-weight: 300;
    }
    .header-badge {
        display: inline-block;
        background: var(--acento);
        color: #1A1A2E;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 12px;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* CARDS */
    .card {
        background: var(--card);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        border: 1px solid var(--borde);
        box-shadow: 0 2px 12px rgba(0,0,0,0.05);
        transition: box-shadow 0.2s ease;
    }
    .card:hover {
        box-shadow: 0 6px 24px rgba(0,0,0,0.10);
    }
    .card-titulo {
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--azul);
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
        background: var(--borde);
    }

    /* EMPRESA HEADER */
    .empresa-header {
        background: linear-gradient(135deg, var(--azul) 0%, #0D3B6E 100%);
        border-radius: 12px;
        padding: 28px;
        color: white;
        margin-bottom: 20px;
    }
    .empresa-nombre {
        font-size: 2rem;
        font-weight: 700;
        margin: 0 0 4px 0;
        letter-spacing: -0.5px;
    }
    .empresa-rubro {
        color: var(--acento);
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .empresa-meta {
        display: flex;
        gap: 24px;
        margin-top: 16px;
        flex-wrap: wrap;
    }
    .empresa-meta-item {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .empresa-meta-label {
        font-size: 0.7rem;
        color: rgba(255,255,255,0.6);
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .empresa-meta-value {
        font-size: 0.95rem;
        font-weight: 600;
        color: white;
    }

    /* KPI CARDS */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-bottom: 20px;
    }
    .kpi-card {
        background: white;
        border-radius: 10px;
        padding: 18px;
        border: 1px solid var(--borde);
        text-align: center;
    }
    .kpi-icono {
        font-size: 1.8rem;
        margin-bottom: 8px;
    }
    .kpi-valor {
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--azul);
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.72rem;
        color: var(--suave);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-top: 4px;
    }

    /* NOTICIAS */
    .noticia-item {
        border-left: 3px solid var(--azul-claro);
        padding: 12px 16px;
        margin-bottom: 12px;
        background: #F8FAFF;
        border-radius: 0 8px 8px 0;
    }
    .noticia-titulo {
        font-weight: 600;
        color: var(--texto);
        font-size: 0.92rem;
        margin-bottom: 4px;
    }
    .noticia-resumen {
        color: var(--suave);
        font-size: 0.83rem;
        line-height: 1.5;
    }
    .noticia-meta {
        font-size: 0.72rem;
        color: var(--azul-claro);
        margin-top: 6px;
        font-family: 'DM Mono', monospace;
    }

    /* EJECUTIVOS */
    .ejecutivo-card {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 0;
        border-bottom: 1px solid var(--borde);
    }
    .ejecutivo-card:last-child {
        border-bottom: none;
    }
    .ejecutivo-avatar {
        width: 42px;
        height: 42px;
        background: linear-gradient(135deg, var(--azul), var(--azul-claro));
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 1rem;
        flex-shrink: 0;
    }
    .ejecutivo-info {
        flex: 1;
    }
    .ejecutivo-nombre {
        font-weight: 600;
        color: var(--texto);
        font-size: 0.9rem;
    }
    .ejecutivo-cargo {
        color: var(--suave);
        font-size: 0.78rem;
        margin-top: 1px;
    }
    .ejecutivo-linkedin {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #0A66C2;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        text-decoration: none;
        flex-shrink: 0;
    }

    /* TAG */
    .tag {
        display: inline-block;
        background: #EEF4FF;
        color: var(--azul);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
        margin: 3px;
        border: 1px solid #D0E0FF;
    }
    .tag-sap {
        background: #FFF7E6;
        color: #B45309;
        border-color: #FDE68A;
    }
    .tag-oportunidad {
        background: #ECFDF5;
        color: #065F46;
        border-color: #A7F3D0;
    }

    /* NO DISPONIBLE */
    .no-disponible {
        color: var(--suave);
        font-style: italic;
        font-size: 0.85rem;
    }

    /* MERCANTIL */
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

    /* FOOTER */
    .footer-info {
        text-align: center;
        color: var(--suave);
        font-size: 0.78rem;
        padding: 20px;
        margin-top: 10px;
        font-family: 'DM Mono', monospace;
    }

    /* Ocultar elementos default de streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    </style>
    """, unsafe_allow_html=True)


# =============================
# HELPERS DE RENDERIZADO
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


# =============================
# RENDERIZADO DEL INFORME
# =============================
def renderizar_informe(datos, linkedin_ejecutivos, mercantil_link):
    # ── Header empresa ──────────────────────────────────────────────
    st.markdown(f"""
    <div class="empresa-header">
        <div class="empresa-rubro">{datos.get('rubro', 'Empresa')}</div>
        <div class="empresa-nombre">{datos.get('nombre_empresa', '')}</div>
        <div style="color:rgba(255,255,255,0.7); font-size:0.88rem; margin-top:6px;">
            {datos.get('descripcion', '')}
        </div>
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
                    <a href="{datos.get('sitio_web', '#')}" target="_blank" style="color:var(--acento);">
                        {datos.get('sitio_web', '—')}
                    </a>
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-icono"></div>
            <div class="kpi-valor">{datos.get('empleados', '—')}</div>
            <div class="kpi-label">Empleados</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icono"></div>
            <div class="kpi-valor">{datos.get('facturacion_anual', '—')}</div>
            <div class="kpi-label">Facturación Anual</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icono"></div>
            <div class="kpi-valor">{datos.get('presencia_geografica', '—')}</div>
            <div class="kpi-label">Presencia</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icono"></div>
            <div class="kpi-valor">{datos.get('importaciones_exportaciones', '—')}</div>
            <div class="kpi-label">Comercio Exterior</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Columnas principales ─────────────────────────────────────────
    col_izq, col_der = st.columns([3, 2], gap="medium")

    with col_izq:
        # Misión y Visión
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo"> Misión & Visión</div>
            <p style="font-size:0.88rem; color:#374151; margin-bottom:10px;">
                <strong>Misión:</strong> {render_valor(datos.get('mision'))}
            </p>
            <p style="font-size:0.88rem; color:#374151; margin:0;">
                <strong>Visión:</strong> {render_valor(datos.get('vision'))}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Tecnología IT
        it = datos.get('tecnologia_it', '')
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo"> Tecnología & IT</div>
            <p style="font-size:0.88rem; color:#374151; margin-bottom:12px;">{render_valor(it)}</p>
        </div>
        """, unsafe_allow_html=True)

        # Oportunidades SAP
        oportunidades = datos.get('oportunidades_sap', '')
        soluciones = datos.get('soluciones_sap', '')
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo"> SAP Intelligence</div>
            <p style="font-size:0.78rem; font-weight:600; color:#B45309; margin-bottom:6px;">SOLUCIONES ACTUALES</p>
            <p style="font-size:0.88rem; color:#374151; margin-bottom:14px;">{render_valor(soluciones)}</p>
            <p style="font-size:0.78rem; font-weight:600; color:#065F46; margin-bottom:6px;">OPORTUNIDADES IDENTIFICADAS</p>
            <p style="font-size:0.88rem; color:#374151; margin:0;">{render_valor(oportunidades)}</p>
        </div>
        """, unsafe_allow_html=True)

        # Noticias
        noticias = datos.get('noticias', [])
        noticias_html = ""
        if noticias:
            for n in noticias:
                titulo = n.get('titulo', '')
                resumen = n.get('resumen', '')
                fecha = n.get('fecha', '')
                fuente = n.get('fuente', '')
                if titulo and "no disponible" not in titulo.lower():
                    noticias_html += f"""
                    <div class="noticia-item">
                        <div class="noticia-titulo">{titulo}</div>
                        <div class="noticia-resumen">{resumen}</div>
                        <div class="noticia-meta"> {fecha} &nbsp;·&nbsp;  {fuente}</div>
                    </div>
                    """
        else:
            noticias_html = '<span class="no-disponible">No se encontraron noticias recientes.</span>'

        st.markdown(f"""
        <div class="card">
            <div class="card-titulo">📰 Noticias Relevantes</div>
            {noticias_html}
        </div>
        """, unsafe_allow_html=True)

    with col_der:
        # Ejecutivos Claude + LinkedIn
        ejecutivos_claude = datos.get('ejecutivos_conocidos', [])

        # Construir mapa de linkedin por nombre (fuzzy básico)
        linkedin_map = {}
        for li in linkedin_ejecutivos:
            nombre_li = li.get('nombre', '').lower()
            linkedin_map[nombre_li] = li

        ejecutivos_html = ""
        if ejecutivos_claude:
            for ej in ejecutivos_claude:
                nombre = ej.get('nombre', '')
                cargo = ej.get('cargo', '')
                if not nombre or "no disponible" in nombre.lower():
                    continue

                # buscar coincidencia en linkedin
                li_match = None
                for key, val in linkedin_map.items():
                    if nombre.split()[0].lower() in key or key.split()[0] in nombre.lower():
                        li_match = val
                        break

                linkedin_btn = ""
                if li_match:
                    linkedin_btn = f'<a class="ejecutivo-linkedin" href="{li_match["link"]}" target="_blank">in LinkedIn</a>'

                ejecutivos_html += f"""
                <div class="ejecutivo-card">
                    <div class="ejecutivo-avatar">{iniciales(nombre)}</div>
                    <div class="ejecutivo-info">
                        <div class="ejecutivo-nombre">{nombre}</div>
                        <div class="ejecutivo-cargo">{cargo}</div>
                    </div>
                    {linkedin_btn}
                </div>
                """

        # Agregar ejecutivos encontrados en LinkedIn que no estén en Claude
        nombres_claude = [e.get('nombre', '').lower() for e in ejecutivos_claude]
        for li in linkedin_ejecutivos:
            nombre_li = li.get('nombre', '')
            ya_incluido = any(nombre_li.split()[0].lower() in nc for nc in nombres_claude if nc)
            if not ya_incluido and nombre_li:
                ejecutivos_html += f"""
                <div class="ejecutivo-card">
                    <div class="ejecutivo-avatar">{iniciales(nombre_li)}</div>
                    <div class="ejecutivo-info">
                        <div class="ejecutivo-nombre">{nombre_li}</div>
                        <div class="ejecutivo-cargo">{li.get('cargo', '')}</div>
                    </div>
                    <a class="ejecutivo-linkedin" href="{li.get('link', '#')}" target="_blank">in LinkedIn</a>
                </div>
                """

        if not ejecutivos_html:
            ejecutivos_html = '<span class="no-disponible">No se encontraron ejecutivos.</span>'

        st.markdown(f"""
        <div class="card">
            <div class="card-titulo"> Directorio Ejecutivo</div>
            {ejecutivos_html}
        </div>
        """, unsafe_allow_html=True)

        # Presencia geográfica e importaciones (extra info)
        st.markdown(f"""
        <div class="card">
            <div class="card-titulo"> Contexto Comercial</div>
            <p style="font-size:0.78rem; font-weight:600; color:#374151; margin-bottom:4px;">PRESENCIA GEOGRÁFICA</p>
            <p style="font-size:0.85rem; color:#6B7280; margin-bottom:12px;">{render_valor(datos.get('presencia_geografica'))}</p>
            <p style="font-size:0.78rem; font-weight:600; color:#374151; margin-bottom:4px;">COMERCIO EXTERIOR</p>
            <p style="font-size:0.85rem; color:#6B7280; margin:0;">{render_valor(datos.get('importaciones_exportaciones'))}</p>
        </div>
        """, unsafe_allow_html=True)

        # Mercantil (solo Chile)
        if mercantil_link:
            st.markdown(f"""
            <div class="card">
                <div class="card-titulo"> Mercantil.com</div>
                <a class="mercantil-link" href="{mercantil_link}" target="_blank">
                     Ver ficha en Mercantil.com
                </a>
            </div>
            """, unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
    <div class="footer-info">
        Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")} &nbsp;·&nbsp;
        SAP Compass Corporate Finder &nbsp;·&nbsp; Powered by Claude Sonnet 4.6
    </div>
    """, unsafe_allow_html=True)


# =============================
# INTERFAZ PRINCIPAL
# =============================
inyectar_css()

# Header
st.markdown("""
<div class="header-principal">
    <div class="header-badge">SAP Compass</div>
    <h1 class="header-titulo">Corporate Intelligence Finder</h1>
    <p class="header-subtitulo">Perfilamiento ejecutivo de cuentas impulsado por IA · Argentina · Chile · Perú · Colombia</p>
</div>
""", unsafe_allow_html=True)

# Formulario
col1, col2, col3 = st.columns([3, 2, 1], gap="medium")
with col1:
    empresa = st.text_input(" Nombre de la empresa", placeholder="Ej: Minera Veta Dorada")
with col2:
    pais = st.selectbox(" País", PAISES_DISPONIBLES)
with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    buscar = st.button(" Generar Perfil", use_container_width=True, type="primary")

st.markdown("---")

# Ejecución
if buscar:
    if not empresa.strip():
        st.error(" Por favor ingresa el nombre de una empresa.")
        st.stop()

    with st.status("Generando perfil corporativo...", expanded=True) as status:
        st.write(" Consultando Claude para información corporativa...")
        datos = consultar_claude(empresa.strip(), pais)

        if datos is None:
            status.update(label="Error al generar el perfil.", state="error")
            st.stop()

        st.write(" Buscando ejecutivos en LinkedIn...")
        linkedin_ejecutivos = buscar_linkedin_ejecutivos(empresa.strip(), pais)

        mercantil_link = ""
        if pais.lower() == "chile":
            st.write(" Buscando en Mercantil.com...")
            mercantil_link = buscar_mercantil(empresa.strip(), pais)

        status.update(label=" Perfil generado exitosamente.", state="complete")

    st.success(f"Perfil de **{empresa}** en **{pais}** generado correctamente.")
    renderizar_informe(datos, linkedin_ejecutivos, mercantil_link)
