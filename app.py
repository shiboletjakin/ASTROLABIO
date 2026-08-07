import streamlit as st
import requests
from bs4 import BeautifulSoup
import swisseph as swe
from datetime import datetime
import pytz
import os
import re
import json
from pathlib import Path
import time

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================
st.set_page_config(
    page_title="🔮 App Astrológica",
    page_icon="🌟",
    layout="wide"
)

# ============================================
# CLASE: SCRAPER DE ASTEROIDES (PASO 1)
# ============================================
class AsteroideScraper:
    def __init__(self):
        self.base_url = "https://www.astro.com"
        self.letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.asteroides_cache = {}
    
    def scrapear_lista(self, letra):
        """Scrapea una lista alfabética de asteroides"""
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
        """Scrapea todas las listas alfabéticas"""
        todos = {}
        total_letras = len(self.letras)
        
        for i, letra in enumerate(self.letras):
            # Actualizar barra de progreso
            progreso.progress((i + 1) / total_letras, f"Scrapeando letra {letra}...")
            
            asteroides = self.scrapear_lista(letra)
            todos.update(asteroides)
            
            # Pequeña pausa para no saturar astro.com
            time.sleep(0.3)
        
        self.asteroides_cache = todos
        return todos
    
    def buscar_por_nombre(self, query):
        """Busca asteroides por nombre en el caché"""
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
        """Devuelve los asteroides más populares de astro.com"""
        populares = {
            1: "Ceres",
            2: "Pallas",
            3: "Juno",
            4: "Vesta",
            2060: "Chiron",
            433: "Eros",
            7066: "Nessus",
            5145: "Pholus",
            5335: "Damocles",
            588: "Achilles",
            944: "Hidalgo",
            1862: "Apollo",
            3200: "Phaethon",
            3753: "Cruithne"
        }
        return populares

# ============================================
# CLASE: CARTA NATAL
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
            # Fallback: UTC directo
            self.jd = swe.julday(año, mes, dia, hora + minuto/60.0, gregflag=1)
        
        # Planetas
        self.planetas_map = {
            'Sol': swe.SUN,
            'Luna': swe.MOON,
            'Mercurio': swe.MERCURY,
            'Venus': swe.VENUS,
            'Marte': swe.MARS,
            'Jupiter': swe.JUPITER,
            'Saturno': swe.SATURN,
            'Urano': swe.URANUS,
            'Neptuno': swe.NEPTUNE,
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
        
        # Calcular posiciones
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
                
                # Encontrar casa
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
                posiciones[nombre] = {
                    'longitud': 0,
                    'signo': '---',
                    'grado': 0,
                    'casa': 0
                }
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
# FUNCIONES AUXILIARES PARA GRÁFICAS
# ============================================
def generar_grafica_svg(carta_data):
    """Genera un SVG profesional de la carta natal"""
    try:
        # Intentar usar Kerykeion
        from kerykeion import AstrologicalSubjectFactory, ChartDataFactory, ChartDrawer
        from io import StringIO
        
        # Crear sujeto
        subject = AstrologicalSubjectFactory.from_birth_data(
            carta_data['nombre'],
            carta_data['año'],
            carta_data['mes'],
            carta_data['dia'],
            carta_data['hora'],
            carta_data['minuto'],
            lng=carta_data['lon'],
            lat=carta_data['lat'],
            tz_str=carta_data['tz'],
            online=False
        )
        
        # Generar datos
        chart_data = ChartDataFactory.create_natal_chart_data(subject)
        
        # Dibujar con tema oscuro
        drawer = ChartDrawer(chart_data, theme="dark")
        svg_string = drawer.generate_svg_string()
        return svg_string
    except Exception as e:
        # Fallback: SVG simple
        return generar_svg_simple(carta_data)

def generar_svg_simple(carta_data):
    """Genera un SVG simple de respaldo"""
    svg = f'''<svg width="500" height="500" xmlns="http://www.w3.org/2000/svg">
    <rect width="500" height="500" fill="#0d0d1a"/>
    <circle cx="250" cy="250" r="210" fill="none" stroke="#2a2a4a" stroke-width="2"/>
    <circle cx="250" cy="250" r="160" fill="none" stroke="#2a2a4a" stroke-width="1"/>
    <circle cx="250" cy="250" r="110" fill="none" stroke="#2a2a4a" stroke-width="1"/>
    <circle cx="250" cy="250" r="60" fill="none" stroke="#2a2a4a" stroke-width="1"/>
    
    <!-- Líneas de aspecto (simplificadas) -->
    <line x1="250" y1="250" x2="250" y2="60" stroke="#ffd700" stroke-width="1" opacity="0.3"/>
    <line x1="250" y1="250" x2="250" y2="440" stroke="#ffd700" stroke-width="1" opacity="0.3"/>
    <line x1="250" y1="250" x2="60" y2="250" stroke="#ffd700" stroke-width="1" opacity="0.3"/>
    <line x1="250" y1="250" x2="440" y2="250" stroke="#ffd700" stroke-width="1" opacity="0.3"/>
    
    <text x="250" y="30" text-anchor="middle" fill="#ffd700" font-size="16" font-weight="bold">{carta_data['nombre']}</text>
    <text x="250" y="490" text-anchor="middle" fill="#888888" font-size="12">Carta Natal</text>
'''
    
    # Añadir planetas en círculo
    colores = {
        'Sol': '#ffd700',
        'Luna': '#e0e0e0',
        'Mercurio': '#b0b0b0',
        'Venus': '#ff6b6b',
        'Marte': '#ff4757',
        'Jupiter': '#ffa502',
        'Saturno': '#2ed573',
        'Urano': '#1e90ff',
        'Neptuno': '#7c5cbf',
        'Pluton': '#ff6348'
    }
    
    planetas_list = ['Sol', 'Luna', 'Mercurio', 'Venus', 'Marte', 'Jupiter', 'Saturno', 'Urano', 'Neptuno', 'Pluton']
    
    for i, planeta in enumerate(planetas_list):
        if planeta in carta_data['posiciones']:
            lon = carta_data['posiciones'][planeta]['longitud']
            angulo = lon - 90
            rad = angulo * 3.14159 / 180
            radio = 185 - (i * 12)
            x = 250 + radio * 0.85 * (rad)
            y = 250 + radio * 0.85 * (rad)
            color = colores.get(planeta, '#ffffff')
            svg += f'<circle cx="{x}" cy="{y}" r="10" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
            svg += f'<text x="{x}" y="{y-14}" text-anchor="middle" fill="#ffffff" font-size="9" font-weight="bold">{planeta[:4]}</text>'
    
    svg += '</svg>'
    return svg

# ============================================
# INTERFAZ DE USUARIO STREAMLIT
# ============================================
st.title("🌟 Generador de Cartas Astrales")
st.markdown("---")

# Verificar estado de los asteroides
if 'asteroides_cargados' not in st.session_state:
    st.session_state.asteroides_cargados = False
    st.session_state.asteroides_cache = {}

# --- COLUMNAS PARA EL FORMULARIO ---
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

# --- BOTÓN PARA CALCULAR ---
if st.button("🔮 Generar Carta Astral", type="primary"):
    with st.spinner("✨ Calculando tu carta astral..."):
        try:
            # Calcular la carta
            carta = CartaNatal(
                nombre, fecha.year, fecha.month, fecha.day,
                hora, minuto, tz, lat, lon
            )
            
            # Guardar datos para gráfica
            carta_data = {
                'nombre': nombre,
                'año': fecha.year,
                'mes': fecha.month,
                'dia': fecha.day,
                'hora': hora,
                'minuto': minuto,
                'tz': tz,
                'lat': lat,
                'lon': lon,
                'posiciones': carta.posiciones
            }
            
            # Guardar en sesión
            st.session_state.carta_data = carta_data
            st.session_state.carta = carta
            
            st.success("✅ Carta astral generada exitosamente")
        except Exception as e:
            st.error(f"❌ Error al generar la carta: {str(e)}")

# --- MOSTRAR RESULTADOS ---
if 'carta' in st.session_state:
    carta = st.session_state.carta
    carta_data = st.session_state.carta_data
    
    st.markdown("---")
    
    # Tabs para organizar
    tab1, tab2, tab3 = st.tabs(["🪐 Gráfica", "📊 Datos", "🔗 Aspectos"])
    
    with tab1:
        st.subheader("🪐 Carta Natal")
        
        # Generar y mostrar SVG
        svg_string = generar_grafica_svg(carta_data)
        st.components.v1.html(f'<div style="background: #0d0d1a; padding: 20px; border-radius: 10px; text-align: center;">{svg_string}</div>', height=550)
        
        # Botón para descargar
        col_desc1, col_desc2 = st.columns(2)
        with col_desc1:
            st.download_button(
                label="⬇️ Descargar como SVG",
                data=svg_string,
                file_name=f"{nombre.replace(' ', '_')}_carta.svg",
                mime="image/svg+xml",
                use_container_width=True
            )
        with col_desc2:
            # Convertir a PNG si es posible
            try:
                import cairosvg
                png_bytes = cairosvg.svg2png(bytestring=svg_string.encode('utf-8'), output_width=1200, output_height=1200)
                st.download_button(
                    label="⬇️ Descargar como PNG",
                    data=png_bytes,
                    file_name=f"{nombre.replace(' ', '_')}_carta.png",
                    mime="image/png",
                    use_container_width=True
                )
            except:
                st.info("💡 La descarga en PNG requiere cairosvg. Usa SVG por ahora.")
    
    with tab2:
        st.subheader("📊 Posiciones Planetarias")
        
        # Tabla de planetas
        data = []
        for planeta, datos in carta.posiciones.items():
            data.append([planeta, datos['signo'], f"{datos['grado']:.2f}°", f"Casa {datos['casa']}"])
        
        st.table(data)
        
        # Datos adicionales
        col_asc, col_mc = st.columns(2)
        with col_asc:
            st.metric("Ascendente", f"{carta.ascendente:.2f}°")
        with col_mc:
            st.metric("Medio Cielo (MC)", f"{carta.mc:.2f}°")
    
    with tab3:
        st.subheader("🔗 Aspectos Principales")
        
        if carta.aspectos:
            for asp in carta.aspectos:
                st.info(f"**{asp['planeta1']}** en **{asp['aspecto']}** con **{asp['planeta2']}** (Orbe: {asp['orbita']}°)")
        else:
            st.info("No se encontraron aspectos principales (orbe 6°)")

# --- SECCIÓN DE ASTEROIDES (PASO 1) ---
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
        
        # Mostrar en columnas
        cols = st.columns(3)
        for i, (num, nom) in enumerate(st.session_state.asteroides_encontrados):
            cols[i % 3].code(f"#{num}: {nom}")
        
        if st.button("➕ Añadir asteroides a mi carta"):
            st.info("💡 Función en desarrollo - Próximamente podrás añadir estos asteroides a tu carta")
    
    # Mostrar asteroides populares
    if st.session_state.asteroides_cargados:
        with st.expander("⭐ Asteroides populares de astro.com"):
            scraper = AsteroideScraper()
            scraper.asteroides_cache = st.session_state.asteroides_cache
            populares = scraper.obtener_asteroides_populares()
            for num, nom in populares.items():
                st.code(f"#{num}: {nom}")

# --- SECCIÓN DE PRONÓSTICO ---
st.markdown("---")
st.subheader("📅 Pronóstico Diario")

fecha_pronostico = st.date_input("Fecha para pronóstico", datetime.now())

if st.button("🔮 Generar Pronóstico", type="secondary"):
    if 'carta' in st.session_state:
        carta = st.session_state.carta
        
        # Calcular tránsitos básicos
        st.info(f"""
        ⭐ **Pronóstico para el {fecha_pronostico.strftime('%d/%m/%Y')}**
        
        Basado en tu carta natal:
        - ☀️ **Sol en {carta.posiciones['Sol']['signo']}**: Momento de tomar iniciativa y brillar
        - 🌙 **Luna en {carta.posiciones['Luna']['signo']}**: Enfoque emocional en el hogar y la familia
        - 💼 **Mercurio en {carta.posiciones['Mercurio']['signo']}**: Buen momento para comunicarse y aprender
        - ❤️ **Venus en {carta.posiciones['Venus']['signo']}**: Energía para el amor y las relaciones
        - 💪 **Marte en {carta.posiciones['Marte']['signo']}**: Momento de tomar acción y ser asertivo
        
        ✨ **Consejo del día**: Aprovecha la energía de {carta.posiciones['Sol']['signo']} para empezar nuevos proyectos.
        """)
    else:
        st.warning("⚠️ Primero genera tu carta natal para obtener el pronóstico")

# --- PIE DE PÁGINA ---
st.markdown("---")
st.caption("🔮 App Astrológica - Versión Demo | Desarrollada con Streamlit")
st.caption("⚡ Paso 1: Scraping de asteroides desde astro.com completado")