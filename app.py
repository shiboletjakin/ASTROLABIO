import streamlit as st
import requests
from bs4 import BeautifulSoup
import swisseph as swe
from datetime import datetime
import pytz
import os
import re
import time
import urllib.request
from pathlib import Path

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================
st.set_page_config(
    page_title="🔮 App Astrológica",
    page_icon="🌟",
    layout="wide"
)

# ============================================
# DESCARGA AUTOMÁTICA DE EFEMÉRIDES (SOLUCIÓN DEL ERROR)
# ============================================
def descargar_efemerides():
    """Descarga los archivos de efemérides de Swiss Ephemeris si no existen"""
    ephe_dir = Path("ephe")
    ephe_dir.mkdir(exist_ok=True)
    
    # Archivos necesarios (los básicos)
    archivos_necesarios = [
        "seas_18.se1",
        "sepl_18.se1",
        "semo_18.se1",
        "seas_18.se1"
    ]
    
    # URLs de descarga (desde el servidor de Astrodienst)
    base_url = "https://www.astro.com/ftp/swisseph/ephe/"
    
    for archivo in archivos_necesarios:
        ruta = ephe_dir / archivo
        if not ruta.exists():
            try:
                st.write(f"⬇️ Descargando {archivo}...")
                urllib.request.urlretrieve(base_url + archivo, ruta)
                st.write(f"✅ {archivo} descargado")
            except Exception as e:
                st.warning(f"⚠️ No se pudo descargar {archivo}: {str(e)[:50]}")
    
    # Configurar la ruta de efemérides para swisseph
    swe.set_ephe_path(str(ephe_dir))

# Intentar descargar efemérides al inicio
try:
    descargar_efemerides()
except Exception as e:
    st.warning(f"⚠️ Advertencia: No se pudieron descargar las efemérides. La app usará datos de respaldo. Error: {str(e)[:50]}")

# ============================================
# CLASE: SCRAPER DE ASTEROIDES
# ============================================
class AsteroideScraper:
    def __init__(self):
        self.base_url = "https://www.astro.com"
        self.letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.asteroides_cache = {}
    
    def scrapear_lista(self, letra):
        url = f"{self.base_url}/astlist_{letra}.htm"
        try:
            with st.spinner(f"🔍 Scrapeando asteroides letra {letra}..."):
                response = requests.get(url, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')
                asteroides = {}
                for link in soup.find_all('a'):
                    texto = link.get_text(strip=True)
                    match = re.match(r'^(\d+)\s+(.+)$', texto)
                    if match:
                        numero = int(match.group(1))
                        nombre = match.group(2).strip()
                        asteroides[numero] = nombre
                return asteroides
        except Exception as e:
            st.warning(f"⚠️ Error en lista {letra}: {str(e)[:50]}")
            return {}
    
    def scrapear_todas(self, progreso):
        todos = {}
        total_letras = len(self.letras)
        for i, letra in enumerate(self.letras):
            progreso.progress((i + 1) / total_letras, f"Scrapeando letra {letra}...")
            asteroides = self.scrapear_lista(letra)
            todos.update(asteroides)
            time.sleep(0.3)
        self.asteroides_cache = todos
        return todos
    
    def buscar_por_nombre(self, query):
        if not self.asteroides_cache:
            return []
        resultados = []
        for num, nom in self.asteroides_cache.items():
            if query.lower() in nom.lower():
                resultados.append((num, nom))
            if len(resultados) >= 50:
                break
        return resultados
    
    def obtener_asteroides_populares(self):
        populares = {
            1: "Ceres", 2: "Pallas", 3: "Juno", 4: "Vesta",
            2060: "Chiron", 433: "Eros", 7066: "Nessus",
            5145: "Pholus", 5335: "Damocles"
        }
        return populares

# ============================================
# CLASE: CARTA NATAL (CON MANEJO DE ERRORES)
# ============================================
class CartaNatal:
    def __init__(self, nombre, año, mes, dia, hora, minuto, tz_str, lat, lon):
        self.nombre = nombre
        self.lat = lat
        self.lon = lon
        self.fecha = f"{año}-{mes:02d}-{dia:02d} {hora:02d}:{minuto:02d}"
        
        # Convertir a UTC
        try:
            local_tz = pytz.timezone(tz_str)
            dt_local = datetime(año, mes, dia, hora, minuto)
            dt_utc = dt_local.astimezone(pytz.UTC)
            self.jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                                dt_utc.hour + dt_utc.minute/60.0, gregflag=1)
        except:
            self.jd = swe.julday(año, mes, dia, hora + minuto/60.0, gregflag=1)
        
        # Planetas
        self.planetas_map = {
            'Sol': swe.SUN, 'Luna': swe.MOON, 'Mercurio': swe.MERCURY,
            'Venus': swe.VENUS, 'Marte': swe.MARS, 'Jupiter': swe.JUPITER,
            'Saturno': swe.SATURN, 'Urano': swe.URANUS, 'Neptuno': swe.NEPTUNE,
            'Pluton': swe.PLUTO
        }
        
        # Calcular casas
        try:
            self.cusps, self.ascmc = swe.houses(self.jd, lat, lon, b'P')
            self.ascendente = self.ascmc[0]
            self.mc = self.ascmc[1]
        except:
            self.cusps = [0] * 12
            self.ascendente = 0
            self.mc = 0
        
        self.posiciones = self._calcular_posiciones()
        self.aspectos = self._calcular_aspectos()
    
    def _calcular_posiciones(self):
        posiciones = {}
        signos = ['Aries','Tauro','Geminis','Cancer','Leo','Virgo',
                 'Libra','Escorpio','Sagitario','Capricornio','Acuario','Piscis']
        for nombre, codigo in self.planetas_map.items():
            try:
                pos = swe.calc_ut(self.jd, codigo, swe.FLG_SWIEPH)[0]
                lon = pos[0]
                signo_idx = int(lon // 30)
                grado = lon % 30
                casa = 1
                for i in range(1, 13):
                    if lon >= self.cusps[i-1]:
                        casa = i
                posiciones[nombre] = {
                    'longitud': round(lon, 2),
                    'signo': signos[signo_idx],
                    'grado': round(grado, 2),
                    'casa': casa
                }
            except:
                posiciones[nombre] = {'longitud': 0, 'signo': '---', 'grado': 0, 'casa': 0}
        return posiciones
    
    def _calcular_aspectos(self, orbe=6):
        aspectos = []
        planetas = list(self.posiciones.keys())
        for i in range(len(planetas)):
            for j in range(i+1, len(planetas)):
                p1 = planetas[i]
                p2 = planetas[j]
                lon1 = self.posiciones[p1]['longitud']
                lon2 = self.posiciones[p2]['longitud']
                diff = abs(lon1 - lon2)
                if diff > 180:
                    diff = 360 - diff
                for angulo, nombre in [(0, 'Conjunción'), (60, 'Sextil'), (90, 'Cuadratura'),
                                       (120, 'Trígono'), (180, 'Oposición')]:
                    if abs(diff - angulo) <= orbe:
                        aspectos.append({
                            'planeta1': p1,
                            'planeta2': p2,
                            'aspecto': nombre,
                            'orbita': round(abs(diff - angulo), 2)
                        })
        return aspectos
    
    def to_dict(self):
        return {
            'nombre': self.nombre,
            'fecha': self.fecha,
            'lat': self.lat,
            'lon': self.lon,
            'ascendente': round(self.ascendente, 2),
            'mc': round(self.mc, 2),
            'posiciones': self.posiciones,
            'aspectos': self.aspectos
        }

# ============================================
# INTERFAZ DE USUARIO
# ============================================
st.title("🌟 Generador de Cartas Astrales")
st.markdown("---")

if 'asteroides_cargados' not in st.session_state:
    st.session_state.asteroides_cargados = False
    st.session_state.asteroides_cache = {}

col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 Datos Personales")
    nombre = st.text_input("Nombre completo", "María González")
    
    st.subheader("📅 Fecha de Nacimiento")
    fecha = st.date_input("Fecha", datetime(1990, 5, 15))
    hora = st.number_input("Hora (formato 24h)", min_value=0, max_value=23, value=14)
    minuto = st.number_input("Minuto", min_value=0, max_value=59, value=30)

with col2:
    st.subheader("📍 Lugar de Nacimiento")
    lat = st.number_input("Latitud (ej: 19.43)", value=19.43, format="%.2f")
    lon = st.number_input("Longitud (ej: -99.13)", value=-99.13, format="%.2f")
    
    tz_options = [
        'America/Mexico_City', 'America/New_York', 'America/Los_Angeles',
        'America/Sao_Paulo', 'Europe/Madrid', 'Europe/London',
        'Europe/Paris', 'Africa/Casablanca', 'Asia/Tokyo', 'Asia/Kolkata',
        'Australia/Sydney', 'Pacific/Auckland'
    ]
    tz = st.selectbox("Zona Horaria", tz_options)

if st.button("🔮 Generar Carta Astral", type="primary"):
    with st.spinner("✨ Calculando tu carta astral..."):
        try:
            carta = CartaNatal(nombre, fecha.year, fecha.month, fecha.day,
                               hora, minuto, tz, lat, lon)
            carta_data = {
                'nombre': nombre, 'año': fecha.year, 'mes': fecha.month,
                'dia': fecha.day, 'hora': hora, 'minuto': minuto,
                'tz': tz, 'lat': lat, 'lon': lon,
                'posiciones': carta.posiciones
            }
            st.session_state.carta_data = carta_data
            st.session_state.carta = carta
            st.success("✅ Carta astral generada exitosamente")
        except Exception as e:
            st.error(f"❌ Error al generar la carta: {str(e)}")

if 'carta' in st.session_state:
    carta = st.session_state.carta
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["🪐 Gráfica", "📊 Datos", "🔗 Aspectos"])
    
    with tab1:
        st.subheader("🪐 Carta Natal")
        # Generar SVG simple
        svg = f'''<svg width="500" height="500" xmlns="http://www.w3.org/2000/svg">
        <rect width="500" height="500" fill="#0d0d1a"/>
        <circle cx="250" cy="250" r="210" fill="none" stroke="#2a2a4a" stroke-width="2"/>
        <circle cx="250" cy="250" r="160" fill="none" stroke="#2a2a4a" stroke-width="1"/>
        <circle cx="250" cy="250" r="110" fill="none" stroke="#2a2a4a" stroke-width="1"/>
        <circle cx="250" cy="250" r="60" fill="none" stroke="#2a2a4a" stroke-width="1"/>
        <text x="250" y="30" text-anchor="middle" fill="#ffd700" font-size="16" font-weight="bold">{carta.nombre}</text>
        <text x="250" y="490" text-anchor="middle" fill="#888" font-size="12">Carta Natal</text>
        '''
        colores = {'Sol':'#ffd700','Luna':'#e0e0e0','Mercurio':'#b0b0b0','Venus':'#ff6b6b',
                   'Marte':'#ff4757','Jupiter':'#ffa502','Saturno':'#2ed573','Urano':'#1e90ff',
                   'Neptuno':'#7c5cbf','Pluton':'#ff6348'}
        planetas_list = ['Sol','Luna','Mercurio','Venus','Marte','Jupiter','Saturno','Urano','Neptuno','Pluton']
        for i, p in enumerate(planetas_list):
            if p in carta.posiciones:
                lon = carta.posiciones[p]['longitud']
                angulo = lon - 90
                rad = angulo * 3.14159 / 180
                radio = 185 - (i * 12)
                x = 250 + radio * 0.85 * rad
                y = 250 + radio * 0.85 * rad
                color = colores.get(p, '#ffffff')
                svg += f'<circle cx="{x}" cy="{y}" r="10" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
                svg += f'<text x="{x}" y="{y-14}" text-anchor="middle" fill="#fff" font-size="9" font-weight="bold">{p[:4]}</text>'
        svg += '</svg>'
        st.components.v1.html(f'<div style="background:#0d0d1a;padding:20px;border-radius:10px;text-align:center;">{svg}</div>', height=550)
        st.download_button(label="⬇️ Descargar SVG", data=svg, file_name=f"{nombre.replace(' ', '_')}_carta.svg", mime="image/svg+xml")
    
    with tab2:
        st.subheader("📊 Posiciones Planetarias")
        data = [[p, d['signo'], f"{d['grado']:.2f}°", f"Casa {d['casa']}"] for p, d in carta.posiciones.items()]
        st.table(data)
        col_asc, col_mc = st.columns(2)
        col_asc.metric("Ascendente", f"{carta.ascendente:.2f}°")
        col_mc.metric("Medio Cielo (MC)", f"{carta.mc:.2f}°")
    
    with tab3:
        st.subheader("🔗 Aspectos Principales")
        if carta.aspectos:
            for asp in carta.aspectos:
                st.info(f"**{asp['planeta1']}** en **{asp['aspecto']}** con **{asp['planeta2']}** (Orbe: {asp['orbita']}°)")
        else:
            st.info("No se encontraron aspectos principales (orbe 6°)")

# ============================================
# SECCIÓN DE ASTEROIDES (PASO 1)
# ============================================
st.markdown("---")
st.subheader("🪐 Catálogo de Asteroides (Paso 1)")
col_busqueda, col_resultados = st.columns([1, 2])
with col_busqueda:
    busqueda = st.text_input("Buscar asteroide por nombre", "Ceres")
    col_boton1, col_boton2 = st.columns(2)
    with col_boton1:
        if st.button("🔍 Buscar", use_container_width=True):
            if st.session_state.asteroides_cargados:
                scraper = AsteroideScraper()
                scraper.asteroides_cache = st.session_state.asteroides_cache
                resultados = scraper.buscar_por_nombre(busqueda)
                if resultados:
                    st.session_state.asteroides_encontrados = resultados
                    st.success(f"✅ {len(resultados)} asteroides encontrados")
                else:
                    st.warning("❌ No se encontraron asteroides")
            else:
                st.warning("⚠️ Primero carga el catálogo")
    with col_boton2:
        if st.button("📥 Cargar Catálogo", use_container_width=True, type="secondary"):
            with st.spinner("📥 Descargando catálogo de asteroides (esto puede tomar 1-2 minutos)..."):
                scraper = AsteroideScraper()
                progress_bar = st.progress(0)
                catalogo = scraper.scrapear_todas(progress_bar)
                st.session_state.asteroides_cache = catalogo
                st.session_state.asteroides_cargados = True
                progress_bar.empty()
                st.success(f"✅ Catálogo cargado: {len(catalogo)} asteroides")

with col_resultados:
    if 'asteroides_encontrados' in st.session_state:
        st.write(f"**Resultados encontrados:** {len(st.session_state.asteroides_encontrados)}")
        cols = st.columns(3)
        for i, (num, nom) in enumerate(st.session_state.asteroides_encontrados):
            cols[i % 3].code(f"#{num}: {nom}")
    if st.session_state.asteroides_cargados:
        with st.expander("⭐ Asteroides populares de astro.com"):
            scraper = AsteroideScraper()
            scraper.asteroides_cache = st.session_state.asteroides_cache
            populares = scraper.obtener_asteroides_populares()
            for num, nom in populares.items():
                st.code(f"#{num}: {nom}")

# ============================================
# SECCIÓN DE PRONÓSTICO
# ============================================
st.markdown("---")
st.subheader("📅 Pronóstico Diario")
fecha_pronostico = st.date_input("Fecha para pronóstico", datetime.now())
if st.button("🔮 Generar Pronóstico", type="secondary"):
    if 'carta' in st.session_state:
        carta = st.session_state.carta
        st.info(f"""
        ⭐ **Pronóstico para el {fecha_pronostico.strftime('%d/%m/%Y')}**
        Basado en tu carta natal:
        - ☀️ **Sol en {carta.posiciones['Sol']['signo']}**: Momento de tomar iniciativa
        - 🌙 **Luna en {carta.posiciones['Luna']['signo']}**: Enfoque emocional en el hogar
        - 💼 **Mercurio en {carta.posiciones['Mercurio']['signo']}**: Buen momento para comunicarse
        - ❤️ **Venus en {carta.posiciones['Venus']['signo']}**: Energía para el amor
        - 💪 **Marte en {carta.posiciones['Marte']['signo']}**: Momento de tomar acción
        ✨ **Consejo**: Aprovecha la energía de {carta.posiciones['Sol']['signo']} para empezar nuevos proyectos.
        """)
    else:
        st.warning("⚠️ Primero genera tu carta natal para obtener el pronóstico")

st.markdown("---")
st.caption("🔮 App Astrológica - Versión Demo | Desarrollada con Streamlit")