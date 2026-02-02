import os
import time
import tempfile
import pdfkit
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from google import genai
import streamlit as st
import requests
import json

# =============================
# CONFIGURACIÓN STREAMLIT
# =============================
st.set_page_config(page_title="SAP Compass — Corporate Finder", layout="wide")

# =============================
# KEYS DESDE STREAMLIT SECRETS
# =============================
API_KEY = st.secrets["API_KEY"]
SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
MODELO = "gemini-2.5-flash"
TIEMPO_ENTRE_PREGUNTAS = 5

# Iniciar cliente Gemini
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    client = None
    st.error("❌ Error inicializando Gemini. Revisa tu API Key en Streamlit Secrets.")
    st.stop()


# =============================
# FUNCIÓN: MERCANTIL.COM
# =============================
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
        "api_key": SERPAPI_KEY
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
        return ""

    return ""


# =============================
# DIRECTORIO SERPAPI
# =============================
def buscar_directorio_serpapi(empresa, pais):
    query = f"Directorio ejecutivo {empresa} {pais} CEO CFO gerente general sitio web LinkedIn"

    params = {
        "engine": "google",
        "q": query,
        "hl": "es",
        "gl": "cl",
        "api_key": SERPAPI_KEY
    }

    r = requests.get("https://serpapi.com/search", params=params)

    if r.status_code != 200:
        return f"No fue posible obtener información del directorio (Código {r.status_code})."

    data = r.json()
    texto = ""

    if "knowledge_graph" in data:
        kg = data["knowledge_graph"]
        if "people" in kg:
            texto += "Personas identificadas en Google:\n"
            for p in kg["people"]:
                nombre = p.get("name", "Sin nombre")
                cargo = p.get("role", "Cargo no especificado")
                link = p.get("link", "")
                texto += f"- {nombre} — {cargo} ({link})\n"

    if "organic_results" in data:
        texto += "\nResultados relevantes:\n"
        for r2 in data["organic_results"][:5]:
            t = r2.get("title", "")
            s = r2.get("snippet", "")
            l = r2.get("link", "")
            texto += f"- {t}: {s} ({l})\n"

    if not texto.strip():
        texto = "No se encontraron datos relevantes del directorio."

    return texto


# =============================
# TEMPLATE HTML (SAP STYLE)
# =============================
TEMPLATE_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ empresa }} — Informe</title>
  <style>
    :root{
      --sap-blue: #0F6CBD;
      --sap-dark-blue: #073B62;
      --sap-yellow: #FFC515;
      --sap-gray: #F5F6F7;
      --card-bg: #ffffff;
      --max-width: 1100px;
    }
    body { font-family: "Segoe UI", Roboto, Arial, sans-serif; background: #efefef; margin: 0; padding: 18px; }
    .portada { max-width: var(--max-width); margin: 10px auto; background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 6px 24px rgba(0,0,0,0.08); }
    .header-sap { background: var(--sap-blue); color: white; padding: 18px; border-radius: 8px; text-align: center; }
    .titulo-empresa { margin: 0; font-size: 28px; font-weight: 700; }
    .subtitulo-info { margin: 6px 0 0; color: #e6f0ff; font-size: 14px; }
    .contenido { display: flex; gap: 20px; margin-top: 18px; flex-wrap: wrap; }
    .col-izquierda { flex: 2; min-width: 300px; }
    .col-derecha { flex: 1; min-width: 240px; }
    .card { background: var(--card-bg); padding: 14px; border-left: 6px solid var(--sap-blue); border-radius: 8px; margin-bottom: 12px; }
    .card h2 { color: var(--sap-dark-blue); margin: 0 0 8px 0; }
    .contenido-texto { color: #222; line-height: 1.45; font-size: 14px; }
    .noticia { border-bottom: 1px solid #eee; padding: 8px 0; }
    a { color: var(--sap-blue); text-decoration: none; font-weight: 600; }
    .footer { margin-top: 18px; text-align: right; color: #666; font-size: 12px; }
  </style>
</head>
<body>
  <div class="portada">
    <div class="header-sap">
      <div class="titulo-empresa">{{ empresa }}</div>
      <div class="subtitulo-info">{{ pais }} — {{ fecha }}</div>
    </div>

    <div class="contenido">
      <div class="col-izquierda">
        <div class="card">
          <h2>Misión y Visión</h2>
          <div class="contenido-texto">{{ mision_vision | safe }}</div>
        </div>

        <div class="card">
          <h2>Noticias principales</h2>
          <div class="noticias">
            {{ noticias | safe }}
          </div>
        </div>
      </div>

      <div class="col-derecha">
        <div class="card">
          <h2>Directivos</h2>
          <div class="contenido-texto">{{ directivos | safe }}</div>
        </div>

        {% if mercantil %}
        <div class="card">
          <h2>Mercantil.com (Chile)</h2>
          <p><a href="{{ mercantil }}" target="_blank">{{ mercantil }}</a></p>
        </div>
        {% endif %}

        <div class="card">
          <h2>Sitio Web Oficial</h2>
          <p><a href="{{ web }}" target="_blank">{{ web }}</a></p>
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


# =============================
# CONSULTA A GEMINI
# =============================
def consultar_gemini(empresa, pais):
    prompts = {
        "directivos": (
            f"Usa SOLO la siguiente información recopilada desde Google/SerpAPI para identificar "
            f"a directivos de {empresa} en {pais}. No inventes nada.\n\n"
            f"=== DATOS GOOGLE ===\n{buscar_directorio_serpapi(empresa, pais)}"
        ),
        "mision_vision": (
            f"Busca misión y visión corporativa de {empresa}. "
            "Si no existe explícitamente, resume propósito corporativo desde 'Quiénes somos'."
        ),
        "noticias": (
            f"Da 3 noticias relevantes de {empresa} en {pais} (últimos 12 meses). "
            "Formato: 1 línea por noticia + link."
        ),
        "web": f"Devuelve SOLO la URL oficial principal de {empresa}."
    }

    resultados = {}

    for clave, prompt in prompts.items():
        resp = client.models.generate_content(
            model=MODELO,
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        resultados[clave] = resp.text.strip()
        time.sleep(TIEMPO_ENTRE_PREGUNTAS)

    return resultados


# =============================
# GENERAR INFORME + PDF
# =============================
def generar_informe(empresa, pais):
    resultados = consultar_gemini(empresa, pais)

    noticias_html = ""
    for item in resultados["noticias"].split("\n"):
        if item.strip():
            noticias_html += f"<div class='noticia'>{item}</div>"

    html = template.render(
        empresa=empresa,
        pais=pais or "—",
        fecha=datetime.now().strftime("%d-%m-%Y"),
        fecha_hora=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        mision_vision=resultados["mision_vision"].replace("\n", "<br>"),
        directivos=resultados["directivos"].replace("\n", "<br>"),
        noticias=noticias_html,
        web=resultados["web"],
        mercantil=buscar_mercantil(empresa, pais)
    )

    # PDFkit
    config = pdfkit.configuration(wkhtmltopdf="/usr/bin/wkhtmltopdf")
    pdf_bytes = pdfkit.from_string(html, False, configuration=config)

    return html, pdf_bytes


# =============================
# INTERFAZ STREAMLIT
# =============================
st.title("🔎 SAP Compass — Corporate Finder")
st.write("Genera informes corporativos estilo SAP usando Gemini + Google SERPAPI")

empresa = st.text_input("Nombre de la Empresa")
pais = st.text_input("País")

if st.button("Generar Informe"):
    if not empresa.strip():
        st.error("Debes ingresar un nombre de empresa.")
        st.stop()

    with st.spinner("Generando informe..."):
        html, pdf_bytes = generar_informe(empresa, pais)

    st.success("Informe generado correctamente.")

    st.markdown("### 📄 Vista previa del informe")
    st.components.v1.html(html, height=900, scrolling=True)

    st.download_button(
        label="📥 Descargar PDF",
        data=pdf_bytes,
        file_name=f"Informe_{empresa}.pdf",
        mime="application/pdf"
    )
