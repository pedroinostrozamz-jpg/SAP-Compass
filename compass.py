import streamlit as st
import os
import time
import tempfile
import pdfkit
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from google import genai
import requests

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Analista Corporativo AI", layout="wide", page_icon="🏛️")

# --- CONFIGURACIÓN DE LLAVES (Secrets de Streamlit) ---
# En Streamlit Cloud, configurarás estas llaves en el panel de Settings
API_KEY = st.secrets.get("GEMINI_KEY", "")
SERPAPI_KEY = st.secrets.get("SERPAPI_KEY", "")
MODELO = "gemini-2.5-flash" # Actualizado a la versión estable
TIEMPO_ENTRE_PREGUNTAS = 5

# Iniciar Cliente Gemini
@st.cache_resource # Esto evita que el cliente se reinicie en cada clic
def get_gemini_client():
    if not API_KEY:
        return None
    try:
        return genai.Client(api_key=API_KEY)
    except Exception:
        return None

client = get_gemini_client()

# ==========================================
# LÓGICA DE BÚSQUEDA (Tus funciones originales)
# ==========================================

def buscar_mercantil(empresa, pais):
    pais = (pais or "").strip().lower()
    if pais not in ["chile", "cl"]:
        return ""
    query = f"{empresa} Chile mercantil"
    params = {"engine": "google", "q": query, "hl": "es", "gl": "cl", "api_key": SERPAPI_KEY}
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
    query = f"Directorio ejecutivo {empresa} {pais} CEO CFO gerente general"
    params = {"engine": "google", "q": query, "hl": "es", "gl": "cl", "api_key": SERPAPI_KEY}
    try:
        r = requests.get("https://serpapi.com/search", params=params)
        if r.status_code != 200: return "Error en SerpAPI"
        data = r.json()
        texto = ""
        if "knowledge_graph" in data and "people" in data["knowledge_graph"]:
            for p in data["knowledge_graph"]["people"]:
                texto += f"- {p.get('name')} — {p.get('role')} ({p.get('link','')})\n"
        for r2 in data.get("organic_results", [])[:5]:
            texto += f"- {r2.get('title')}: {r2.get('snippet')} ({r2.get('link')})\n"
        return texto or "No se encontraron datos."
    except:
        return "Error al consultar directorio."

def consultar_gemini(empresa, pais):
    if not client:
        st.error("Error: API Key de Gemini no configurada.")
        return None

    directorio_google = buscar_directorio_serpapi(empresa, pais)
    prompts = {
        "directivos": f"Identifica directivos de {empresa} en {pais} usando estos datos: {directorio_google}. Solo entrega lista limpia.",
        "mision_vision": f"Busca o resume la Misión y Visión de {empresa}.",
        "noticias": f"Busca 3 noticias de negocios sobre {empresa} en {pais} (últimos 12 meses). Resume en 1 línea con link.",
        "web": f"URL oficial de {empresa}. Solo la URL."
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

# ==========================================
# GENERACIÓN DE INFORME Y PDF
# ==========================================

TEMPLATE_HTML = """
<style>
    body { font-family: sans-serif; padding: 20px; background: #f4f4f4; }
    .container { background: white; padding: 30px; border-radius: 10px; border-top: 10px solid #0F6CBD; }
    h1 { color: #073B62; }
    .card { border-left: 5px solid #0F6CBD; padding-left: 15px; margin-bottom: 20px; }
</style>
<div class="container">
    <h1>Informe: {{ empresa }}</h1>
    <p>{{ pais }} | {{ fecha }}</p>
    <div class="card"><h3>Misión y Visión</h3><p>{{ mision_vision | safe }}</p></div>
    <div class="card"><h3>Directivos</h3><p>{{ directivos | safe }}</p></div>
    <div class="card"><h3>Noticias</h3><p>{{ noticias | safe }}</p></div>
    <p> <b>Web:</b> <a href="{{ web }}">{{ web }}</a></p>
</div>
"""

def generar_informe(empresa, pais):
    resultados = consultar_gemini(empresa, pais)
    if not resultados: return None, None
    
    link_mercantil = buscar_mercantil(empresa, pais)
    env = Environment(autoescape=select_autoescape(['html']))
    template = env.from_string(TEMPLATE_HTML)
    
    html = template.render(
        empresa=empresa, pais=pais, fecha=datetime.now().strftime("%d-%m-%Y"),
        mision_vision=resultados["mision_vision"].replace("\n", "<br>"),
        directivos=resultados["directivos"].replace("\n", "<br>"),
        noticias=resultados["noticias"].replace("\n", "<br>"),
        web=resultados["web"]
    )
    
    # Configuración de PDF (Ajustada para servidor Linux)
    config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')
    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        pdfkit.from_string(html, tmp_pdf.name, configuration=config)
        return html, tmp_pdf.name
    except:
        return html, None

# ==========================================
# INTERFAZ DE USUARIO (Streamlit)
# ==========================================

st.sidebar.title(" Panel de Control")
empresa_input = st.sidebar.text_input("Nombre de la Empresa", placeholder="Ej: Google")
pais_input = st.sidebar.text_input("País", placeholder="Ej: Chile")
buscar_btn = st.sidebar.button("Generar Informe Ejecutivo", type="primary")

st.title("🏛️ Buscador Corporativo AI")
st.info("Introduce los datos en la izquierda para comenzar el análisis.")

if buscar_btn:
    if not empresa_input or not pais_input:
        st.warning(" Por favor completa ambos campos.")
    else:
        with st.status(" Investigando en tiempo real...", expanded=True) as status:
            html_res, pdf_res = generar_informe(empresa_input, pais_input)
            status.update(label=" Informe Finalizado", state="complete")
        
        # Mostrar el resultado en la App
        st.components.v1.html(html_res, height=600, scrolling=True)
        
        # Botón de descarga
        if pdf_res:
            with open(pdf_res, "rb") as f:
                st.download_button(" Descargar PDF", f, file_name=f"Informe_{empresa_input}.pdf")
