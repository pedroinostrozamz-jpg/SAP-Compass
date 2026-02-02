import streamlit as st
import json
import datetime
import requests
from jinja2 import Template
import pdfkit
from serpapi import GoogleSearch
from google import genai

# ----------------------------
# CONFIGURACIÓN STREAMLIT
# ----------------------------
st.set_page_config(page_title="Informe Corporativo", layout="wide")

# ----------------------------
# CONFIGURACIÓN API KEYS
# ----------------------------
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
SERPAPI_KEY = st.secrets["SERPAPI_KEY"]

client = genai.Client(api_key=GEMINI_API_KEY)

# ----------------------------
# TEMPLATE HTML SAP (COMPLETO)
# ----------------------------
TEMPLATE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f6f9; }
.header { background: #003366; padding: 20px; color: white; text-align: center; }
.container { display: flex; padding: 20px; }
.col { width: 50%; padding: 20px; }
.card { background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.15); }
h2 { color: #003366; margin-top: 0; }
ul { padding-left: 18px; }
</style>
</head>
<body>

<div class="header">
  <h1>Informe Corporativo: {{ empresa }}</h1>
  <p>{{ fecha }} — País: {{ pais }}</p>
</div>

<div class="container">
  <div class="col">

    {% if mision_vision %}
    <div class="card">
      <h2>Misión y Visión</h2>
      <p>{{ mision_vision }}</p>
    </div>
    {% endif %}

    {% if directivos %}
    <div class="card">
      <h2>Directivos Principales</h2>
      <ul>
        {% for d in directivos %}
          <li>
            <strong>{{ d.nombre }}</strong> — {{ d.cargo }}
            {% if d.linkedin %}
            <br><a href="{{ d.linkedin }}" target="_blank">LinkedIn</a>
            {% endif %}
          </li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

    {% if noticias %}
    <div class="card">
      <h2>Noticias Relevantes</h2>
      <ul>
        {% for n in noticias %}
        <li>{{ n.titulo }} — <a href="{{ n.link }}" target="_blank">Enlace</a></li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}

  </div>


  <div class="col">

    {% if web %}
    <div class="card">
      <h2>Página Corporativa</h2>
      <a href="{{ web }}" target="_blank">{{ web }}</a>
    </div>
    {% endif %}

    {% if mercantil %}
    <div class="card">
      <h2>Mercantil (Chile)</h2>
      <a href="{{ mercantil }}" target="_blank">{{ mercantil }}</a>
    </div>
    {% endif %}

  </div>
</div>

</body>
</html>
"""


# ----------------------------
# FUNCIONES DE CONSULTA
# ----------------------------

def serpapi_busqueda_linkedin(nombre, empresa, pais):
    """Devuelve un link REAL de LinkedIn usando SerpAPI."""
    try:
        query = f"{nombre} {empresa} {pais} site:linkedin.com"
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_KEY
        }
        search = GoogleSearch(params)
        results = search.get_dict()

        if "organic_results" in results:
            for r in results["organic_results"]:
                link = r.get("link", "")
                if "linkedin.com/in" in link:
                    return link

    except:
        return None

    return None


def generar_directivos(empresa, pais):
    """Obtiene directivos reales vía Gemini + valida LinkedIn vía SerpAPI."""
    prompt = f"""
    Lista 5 directivos REALES de {empresa} en {pais}.
    Devuelve SOLO un JSON válido con:
    - nombre
    - cargo

    Ejemplo:
    [
      {{"nombre": "Jane Doe", "cargo": "Gerente General"}},
      ...
    ]

    No inventes personas. Si no existen específicamente en {pais}, usa los directivos del país más cercano o la matriz.
    """

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        try:
            directivos = json.loads(text)
        except:
            import re
            m = re.search(r"\[.*\]", text, re.DOTALL)
            if m:
                directivos = json.loads(m.group(0))
            else:
                return []

        # Agregar LinkedIn verificado por SerpAPI
        for d in directivos:
            link = serpapi_busqueda_linkedin(d["nombre"], empresa, pais)
            d["linkedin"] = link

        return directivos

    except:
        return []


def generar_mision_vision(empresa, pais):
    prompt = f"""
    Entrega la misión y visión de {empresa} en {pais}.
    Debe ser texto conciso en 8 líneas máximo.
    No inventes información.
    """
    try:
        r = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return r.text.strip()
    except:
        return ""


def generar_noticias(empresa, pais):
    prompt = f"""
    Devuelve exactamente 3 noticias REALES de negocios sobre {empresa} en {pais},
    ocurridas en los últimos 12 meses.
    Cada noticia debe tener:
    - título
    - link real (obligatorio)

    Formato JSON.
    """
    try:
        r = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        text = r.text.strip()
        try:
            return json.loads(text)
        except:
            import re
            m = re.search(r"\[.*\]", text, re.DOTALL)
            return json.loads(m.group(0)) if m else []
    except:
        return []


def buscar_web_corporativa(empresa, pais):
    prompt = f"""
    Devuélveme el link de la página corporativa REAL de {empresa} en {pais}.
    Solo URL exacta. Nada más.
    """
    try:
        r = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return r.text.strip()
    except:
        return ""


def buscar_mercantil(empresa, pais):
    params = {
        "engine": "google",
        "q": f"{empresa} sitio:mercantil.com",
        "api_key": SERPAPI_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    if "organic_results" in results:
        for r in results["organic_results"]:
            if "mercantil.com" in r.get("link", ""):
                return r["link"]

    return ""


# ----------------------------
# INTERFAZ STREAMLIT
# ----------------------------

st.title("📄 Generador de Informe Corporativo")

empresa = st.text_input("Nombre de la empresa")
pais = st.text_input("País del análisis", value="Chile")

if st.button("Generar Informe"):
    if not empresa or not pais:
        st.error("Debes ingresar empresa y país.")
        st.stop()

    with st.spinner("Generando informe..."):

        mision_vision = generar_mision_vision(empresa, pais)
        directivos = generar_directivos(empresa, pais)
        noticias = generar_noticias(empresa, pais)
        web = buscar_web_corporativa(empresa, pais)
        mercantil = buscar_mercantil(empresa, pais)

        template = Template(TEMPLATE_HTML)
        html_final = template.render(
            empresa=empresa,
            pais=pais,
            fecha=datetime.date.today().strftime("%d-%m-%Y"),
            mision_vision=mision_vision,
            directivos=directivos,
            noticias=noticias,
            web=web,
            mercantil=mercantil
        )

        # Mostrar HTML en pantalla
        st.components.v1.html(html_final, height=1100, scrolling=True)

        # Descargar PDF
        pdf_path = f"Informe_{empresa}.pdf"
        pdfkit.from_string(html_final, pdf_path)

        with open(pdf_path, "rb") as f:
            btn = st.download_button(
                label="📥 Descargar PDF",
                data=f,
                file_name=pdf_path,
                mime="application/pdf"
            )
