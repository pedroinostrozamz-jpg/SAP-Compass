import streamlit as st
import requests
import json
import os
import time
import tempfile
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from google import genai

# ===========================
# CONFIGURACIÓN STREAMLIT
# ===========================
st.set_page_config(
    page_title="Informe Corporativo estilo SAP — Gemini + SerpAPI",
    layout="wide",
)

# ===========================
# CARGA DE SECRETS
# ===========================
API_KEY = st.secrets["API_KEY"]
SERPAPI_KEY = st.secrets["SERPAPI_KEY"]

MODELO = "gemini-2.5-flash"
TIEMPO_ENTRE_PREGUNTAS = 5

# Inicializar Gemini
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    client = None
    st.error("Error inicializando Gemini. Revisa tu API KEY.")


# ===========================
# FUNCIÓN: Buscar Mercantil
# ===========================
def buscar_mercantil(empresa, pais):
    pais = (pais or "").strip().lower()

    if pais not in ["chile", "cl"]:
        return ""

    query = f"{empresa} Chile mercantil"

    params = {
        "engine": "google",
        "q": query,
        "hl": "es",
        "gl": "cl",
        "api_key": SERPAPI_KEY,
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params)
        if r.status_code != 200:
            return ""

        data = r.json()

        if "organic_results" in data:
            for item in data["organic_results"]:
                link = item.get("link", "")
                if "mercantil.com" in link.lower():
                    return link

    except:
        pass

    return ""


# ===========================
# FUNCIÓN: Directorio SerpAPI
# ===========================
def buscar_directorio_serpapi(empresa, pais):
    query = f"Directorio ejecutivo {empresa} {pais} CEO CFO gerente general LinkedIn sitio web"

    params = {
        "engine": "google",
        "q": query,
        "hl": "es",
        "gl": "cl",
        "api_key": SERPAPI_KEY,
    }

    r = requests.get("https://serpapi.com/search", params=params)

    if r.status_code != 200:
        return f"No fue posible obtener directorio. Código: {r.status_code}"

    data = r.json()
    texto = ""

    # Extraer Knowledge Graph
    if "knowledge_graph" in data:
        kg = data["knowledge_graph"]
        if "people" in kg:
            texto += "Personas identificadas:\n"
            for p in kg["people"]:
                nombre = p.get("name", "Sin nombre")
                cargo = p.get("role", "Cargo no especificado")
                link = p.get("link", "")
                texto += f"- {nombre} — {cargo} ({link})\n"

    # Extraer resultados orgánicos
    if "organic_results" in data:
        texto += "\nResultados relevantes:\n"
        for r2 in data["organic_results"][:5]:
            t = r2.get("title", "")
            s = r2.get("snippet", "")
            l = r2.get("link", "")
            texto += f"- {t}: {s} ({l})\n"

    if not texto.strip():
        texto = "No se encontraron directivos en Google."

    return texto


# ===========================
# TEMPLATE HTML COMPATIBLE
# ===========================

TEMPLATE_HTML = """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>{{ empresa }} — Informe</title>

<style>

body {
    font-family: "Segoe UI", Arial, sans-serif;
    background: #f5f5f5;
    margin: 0;
    padding: 20px;
}

.wrapper {
    width: 100%;
    max-width: 1100px;
    margin: auto;
    background: white;
    padding: 18px;
    border: 1px solid #ccc;
}

.header {
    background: #0F6CBD;
    color: white;
    padding: 18px;
    text-align: center;
}

.header-title {
    font-size: 26px;
    font-weight: bold;
}

.sub {
    font-size: 14px;
    margin-top: 4px;
}

.columns {
    width: 100%;
}

.col-left {
    width: 68%;
    float: left;
    margin-right: 2%;
}

.col-right {
    width: 30%;
    float: left;
}

.card {
    background: #ffffff;
    border-left: 6px solid #0F6CBD;
    padding: 12px;
    margin-bottom: 12px;
}

.card h2 {
    color: #073B62;
    margin: 0 0 6px 0;
}

.footer {
    clear: both;
    text-align: right;
    margin-top: 25px;
    font-size: 12px;
    color: #555;
}

a {
    color: #0F6CBD;
    text-decoration: none;
}

.noticia {
    border-bottom: 1px solid #eee;
    padding: 6px 0;
}

</style>
</head>

<body>
<div class="wrapper">

    <div class="header">
        <div class="header-title">{{ empresa }}</div>
        <div class="sub">{{ pais }} — {{ fecha }}</div>
    </div>

    <div class="columns">

        <!-- Columna izquierda -->
        <div class="col-left">

            <div class="card">
                <h2>Misión y Visión</h2>
                <div>{{ mision_vision | safe }}</div>
            </div>

            <div class="card">
                <h2>Noticias</h2>
                <div>{{ noticias | safe }}</div>
            </div>

        </div>

        <!-- Columna derecha -->
        <div class="col-right">

            <div class="card">
                <h2>Directivos</h2>
                <div>{{ directivos | safe }}</div>
            </div>

            {% if mercantil %}
            <div class="card">
                <h2>Mercantil.com</h2>
                <a href="{{ mercantil }}" target="_blank">{{ mercantil }}</a>
            </div>
            {% endif %}

            <div class="card">
                <h2>Sitio Web Oficial</h2>
                <a href="{{ web }}" target="_blank">{{ web }}</a>
            </div>

        </div>

    </div>

    <div class="footer">
        Generado: {{ fecha_hora }}
    </div>

</div>
</body>
</html>
"""

env = Environment(loader=FileSystemLoader("."), autoescape=select_autoescape(['html', 'xml']))
template = env.from_string(TEMPLATE_HTML)


# ===========================
# CONSULTA A GEMINI
# ===========================
def consultar_gemini(empresa, pais):
    if not client:
        raise RuntimeError("Gemini no inicializado.")

    directorio_google = buscar_directorio_serpapi(empresa, pais)

    prompts = {
        "directivos": (
            f"Con la siguiente información obtenida de Google/SerpAPI, identifica únicamente los directivos reales "
            f"de {empresa} en {pais}. NO inventes datos.\n\n"
            f"=== DATOS GOOGLE ===\n{directorio_google}\n\n"
            "Devuelve nombre, cargo y enlace si existe."
        ),
        "mision_vision": (
            f"Obtén la misión y visión corporativa de {empresa}. Si no existen explícitamente, resume propósito corporativo."
        ),
        "noticias": (
            f"Dame exactamente 3 noticias relevantes de negocios sobre {empresa} en {pais}, de los últimos 12 meses, "
            "cada una con un resumen breve y link."
        ),
        "web": (
            f"Dime la URL oficial de {empresa}. Solo la URL."
        ),
    }

    resultados = {}

    for clave, prompt in prompts.items():
        try:
            resp = client.models.generate_content(
                model=MODELO,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
            )
            resultados[clave] = resp.text.strip()
        except Exception as e:
            resultados[clave] = f"Error: {e}"

        time.sleep(TIEMPO_ENTRE_PREGUNTAS)

    return resultados


# ===========================
# Generar reporte + PDF
# ===========================
def generar_informe(empresa, pais):
    empresa = (empresa or "").strip()
    pais = (pais or "").strip()

    resultados = consultar_gemini(empresa, pais)

    # Mercantil
    link_mercantil = buscar_mercantil(empresa, pais)

    # Noticias → HTML
    noticias_html = ""
    items = resultados["noticias"].split("\n")
    for item in items:
        if item.strip():
            noticias_html += f"<div class='noticia'>{item}</div>"

    fecha = datetime.now().strftime("%d-%m-%Y")
    fecha_hora = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    html = template.render(
        empresa=empresa,
        pais=pais,
        fecha=fecha,
        fecha_hora=fecha_hora,
        mision_vision=resultados["mision_vision"].replace("\n", "<br>"),
        directivos=resultados["directivos"].replace("\n", "<br>"),
        noticias=noticias_html,
        web=resultados["web"],
        mercantil=link_mercantil,
    )

    # Crear PDF con WeasyPrint
    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    HTML(string=html).write_pdf(tmp_pdf.name)

    return html, tmp_pdf.name


# ===========================
# UI STREAMLIT
# ===========================
st.title("📄 Informe Corporativo — SAP Style (Gemini + SerpAPI)")

empresa = st.text_input("Empresa")
pais = st.text_input("País")
btn = st.button("Generar Informe")

if btn:
    if not empresa.strip():
        st.error("Debe ingresar una empresa.")
        st.stop()

    with st.spinner("Generando informe corporativo..."):
        html, pdf_path = generar_informe(empresa, pais)

    st.success("Informe generado correctamente.")

    st.download_button(
        "📥 Descargar PDF",
        data=open(pdf_path, "rb").read(),
        file_name=f"Informe_{empresa}.pdf",
        mime="application/pdf",
    )

    st.markdown("### Vista previa HTML")
    st.markdown(html, unsafe_allow_html=True)
