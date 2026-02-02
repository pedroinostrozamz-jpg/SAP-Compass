import streamlit as st
import os
import time
import tempfile
import pdfkit
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from google import genai
import requests

# =============================
# CONFIG DE STREAMLIT
# =============================
st.set_page_config(page_title="Analista Corporativo AI", layout="wide", page_icon="🏛️")

API_KEY = st.secrets.get("GEMINI_KEY", "")
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")
MODELO = "gemini-2.5-flash"
TIEMPO_ENTRE_PREGUNTAS = 4

# =============================
# CLIENTE GEMINI
# =============================
@st.cache_resource
def get_gemini_client():
    if not API_KEY:
        return None
    try:
        return genai.Client(api_key=API_KEY)
    except:
        return None

client = get_gemini_client()

# =============================
# FUNCIONES DE BÚSQUEDA
# =============================

def buscar_mercantil(empresa, pais):
    # Solo si el país es Chile
    if pais.strip().lower() not in ["chile", "cl"]:
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
        r = requests.get("https://serpapi.com/search", params=params)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("organic_results", []):
                link = item.get("link", "")
                if "mercantil.com" in link.lower():
                    return link
    except:
        pass

    return ""


def buscar_directorio_serpapi(empresa, pais):
    query = f"Directorio ejecutivo {empresa} {pais} CEO CFO Gerente General"
    params = {
        "engine": "google",
        "q": query,
        "hl": "es",
        "gl": "cl",
        "api_key": SERPAPI_KEY
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params)
        if r.status_code != 200:
            return ""

        data = r.json()
        texto = ""

        # Knowledge graph
        if "knowledge_graph" in data and "people" in data["knowledge_graph"]:
            for p in data["knowledge_graph"]["people"]:
                texto += f"- {p.get('name')} — {p.get('role')}\n"

        # Primeros orgs
        for r2 in data.get("organic_results", [])[:5]:
            texto += f"- {r2.get('title')} — {r2.get('snippet')}\n"

        return texto or ""
    except:
        return ""


def consultar_gemini(empresa, pais):
    if not client:
        st.error("Error: Falta configurar GEMINI_KEY en Secrets.")
        return None

    # Entrada obligatoria del directorio
    directorio_google = buscar_directorio_serpapi(empresa, pais)

    prompts = {
        "directivos": (
            f"Usa SOLO esta información real encontrada: {directorio_google}."
            f" Devuélveme una lista limpia de directivos de {empresa} en {pais}. "
            f"Si aparece información de otro país, DESCÁRTALA."
        ),

        "mision_vision": (
            f"Busca y resume EXCLUSIVAMENTE la misión y visión de {empresa} en {pais}. "
            f"Si aparecen versiones de otros países, IGNÓRALAS."
        ),

        "noticias": (
            f"Busca EXCLUSIVAMENTE noticias de negocios sobre {empresa} en {pais}. "
            f"NO incluyas noticias de otros países. "
            f"Devuélveme exactamente 3 noticias del último año, cada una en 1 línea con su link."
        ),

        "web": (
            f"Identifica la URL oficial de la empresa {empresa} en {pais}. "
            f"Devuelve SOLO la URL."
        )
    }

    resultados = {}
    for clave, prompt in prompts.items():
        try:
            resp = client.models.generate_content(model=MODELO, contents=prompt)
            resultados[clave] = resp.text.strip()
            time.sleep(TIEMPO_ENTRE_PREGUNTAS)
        except Exception as e:
            resultados[clave] = f"Error: {e}"

    return resultados


# =============================
# TEMPLATE HTML CORPORATIVO SAP (VERSIÓN COLAB)
# =============================

TEMPLATE_HTML = """
<style>
    body {
        background-color: #f0f2f5;
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 0;
    }
    .contenedor {
        width: 90%;
        margin: auto;
        margin-top: 20px;
        background: white;
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border-left: 10px solid #0F6CBD;
    }
    h1 {
        color: #073B62;
        margin-bottom: 5px;
    }
    h2 {
        color: #0F6CBD;
        margin-top: 20px;
    }
    .card {
        border-left: 6px solid #0F6CBD;
        padding: 15px;
        background: #f7f9fc;
        margin-bottom: 20px;
        border-radius: 8px;
    }
    .seccion {
        margin-top: 30px;
    }
</style>

<div class="contenedor">

    <h1>Informe: {{ empresa }}</h1>
    <p><b>{{ pais }}</b> | {{ fecha }}</p>

    {% if mercantil %}
    <div class="card">
        <h2>Registro Mercantil (Chile)</h2>
        <a href="{{ mercantil }}">{{ mercantil }}</a>
    </div>
    {% endif %}

    <div class="card">
        <h2>Misión y Visión</h2>
        <p>{{ mision_vision | safe }}</p>
    </div>

    <div class="card">
        <h2>Directivos</h2>
        <p>{{ directivos | safe }}</p>
    </div>

    <div class="card">
        <h2>Noticias Recientes</h2>
        <p>{{ noticias | safe }}</p>
    </div>

    <div class="card">
        <h2>Web Oficial</h2>
        <a href="{{ web }}">{{ web }}</a>
    </div>

</div>
"""


# =============================
# GENERACIÓN DEL INFORME + PDF
# =============================

def generar_informe(empresa, pais):
    resultados = consultar_gemini(empresa, pais)
    if not resultados:
        return None, None

    link_mercantil = buscar_mercantil(empresa, pais)

    env = Environment(autoescape=select_autoescape(['html']))
    template = env.from_string(TEMPLATE_HTML)

    html = template.render(
        empresa=empresa,
        pais=pais,
        fecha=datetime.now().strftime("%d-%m-%Y"),
        mision_vision=resultados.get("mision_vision", "").replace("\n", "<br>"),
        directivos=resultados.get("directivos", "").replace("\n", "<br>"),
        noticias=resultados.get("noticias", "").replace("\n", "<br>"),
        web=resultados.get("web", ""),
        mercantil=link_mercantil
    )

    config = pdfkit.configuration(wkhtmltopdf="/usr/bin/wkhtmltopdf")
    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

    try:
        pdfkit.from_string(html, tmp_pdf.name, configuration=config)
        return html, tmp_pdf.name
    except:
        return html, None


# =============================
# UI STREAMLIT
# =============================

st.sidebar.title(" Panel de Control")
empresa_input = st.sidebar.text_input("Empresa", placeholder="Ej: Falabella")
pais_input = st.sidebar.text_input("País", placeholder="Ej: Chile")
btn = st.sidebar.button("Generar Informe", type="primary")

st.title("Generador de Informes Empresariales AI")
st.info("Completa los datos en el panel izquierdo para generar el informe corporativo.")

if btn:
    if not empresa_input or not pais_input:
        st.warning("Faltan datos obligatorios.")
    else:
        with st.status("Generando informe...", expanded=True) as status:
            html_res, pdf_res = generar_informe(empresa_input, pais_input)
            status.update(label="Informe listo", state="complete")

        st.components.v1.html(html_res, height=750, scrolling=True)

        if pdf_res:
            with open(pdf_res, "rb") as f:
                st.download_button(
                    "📄 Descargar PDF",
                    f,
                    file_name=f"Informe_{empresa_input}.pdf"
                )
