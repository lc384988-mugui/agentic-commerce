import streamlit as st
from supabase import create_client, Client
from groq import Groq
import re
import pandas as pd
import plotly.express as px
from duckduckgo_search import DDGS
import yfinance as yf
import hashlib
import time

# ==========================================
# 1. CONFIGURACIÓN (NUBE Y GROQ)
# ==========================================
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# ==========================================
# 2. BASE DE DATOS EN LA NUBE (SUPABASE)
# ==========================================
def guardar_transaccion(producto, comprador, vendedor, monto, estado, hash_contrato):
    data = {
        "producto": producto, "comprador": comprador, "vendedor": vendedor, 
        "monto": monto, "estado": estado, "hash_contrato": hash_contrato
    }
    supabase.table("transacciones").insert(data).execute()

def obtener_transacciones():
    response = supabase.table("transacciones").select("*").execute()
    if response.data:
        return pd.DataFrame(response.data)
    return pd.DataFrame()

# ==========================================
# 3. ORÁCULO Y BÚSQUEDA
# ==========================================
def obtener_precio_mercado():
    try:
        ticker = yf.Ticker("BTC-USD")
        precio = ticker.history(period="1d")['Close'].iloc[-1]
        return f"${precio:,.2f} USD"
    except:
        return "Datos no disponibles"

def buscar_precio_real(producto):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"precio promedio de {producto} NZD", max_results=2))
            if results:
                return results[0]['body']
    except:
        pass
    return "No se encontraron datos exactos, usa tu instinto."

# ==========================================
# 4. AGENTES DE IA
# ==========================================
def chatear_con_agente(rol, producto, limite, personalidad, historial, info_web):
    if rol == "Vendedor":
        prompt = f"Eres un vendedor de {producto}. Precio mínimo: ${limite}. Personalidad: {personalidad}. Info del mercado: {info_web}. SOLO discute el precio. Si aceptas, di exactamente: 'Acepto vender por $X'."
    elif rol == "Auditor":
        prompt = f"Eres un Auditor Legal de IA experto en comercio B2B. Se está negociando {producto} por un monto de ${limite}. Redacta un mini-contrato legal (máximo 2 líneas) validando la transacción. Termina siempre con: 'Trato Aprobado'."
    else:
        prompt = f"Eres un comprador de {producto}. Presupuesto máximo: ${limite}. Personalidad: {personalidad}. Info del mercado: {info_web}. SOLO discute el precio. Si aceptas, di exactamente: 'Acepto comprar por $X'."

    chat = client.chat.completions.create(
        messages=[{"role": "system", "content": prompt}] + historial,
        model="openai/gpt-oss-20b", 
    )
    return chat.choices[0].message.content

# ==========================================
# 5. INTERFAZ WEB PREMIUM
# ==========================================
st.set_page_config(page_title="Agentic AI SaaS", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&display=swap');
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-color: #050505; font-family: 'Space Grotesk', sans-serif; }
    h1 { background: -webkit-linear-gradient(45deg, #00ffcc, #0099ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 3rem !important; }
    div[data-baseweb="input"] { background-color: #111 !important; border: 1px solid #333 !important; border-radius: 8px !important; }
    div[data-baseweb="input"] > input { color: #00ffcc !important; -webkit-text-fill-color: #00ffcc !important; }
    div[data-baseweb="select"] > div { background-color: #111 !important; border: 1px solid #333 !important; color: #00ffcc !important; }
    .stButton>button { background: linear-gradient(90deg, #00ffcc 0%, #0099ff 100%) !important; color: #000 !important; font-weight: 800 !important; border-radius: 8px !important; border: none !important; }
    .stButton>button:hover { box-shadow: 0 0 15px rgba(0, 255, 204, 0.6) !important; }
    [data-testid="stChatMessage"] { background-color: #0a0a0a !important; border-left: 4px solid #00ffcc !important; border-radius: 0px 10px 10px 0px !important; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .stAlert { background-color: #111 !important; border: 1px solid #00ffcc !important; color: #fff !important; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Agentic Commerce SaaS")
st.markdown("Comercio B2B autónomo. Blindado por IA y validado con Firma Digital.")

# LOGIN
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.subheader("🔒 Acceso Corporativo")
    usuario = st.text_input("Usuario", "admin")
    password = st.text_input("Contraseña", type="password", value="1234")
    if st.button("Ingresar al Sistema"):
        if password == "1234":
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta. (Usa: 1234)")
    st.stop()

# BARRA LATERAL
with st.sidebar:
    st.header("⚙️ Panel de Control")
    producto = st.text_input("Producto a negociar:", "Licencia de Software")
    presupuesto_c = st.number_input("Presupuesto Comprador ($)", value=100)
    precio_v = st.number_input("Mínimo Vendedor ($)", value=80)
    personalidad = st.selectbox("Personalidad de los agentes:", ["Profesional", "Agresivo", "Amigable"])
    
    st.markdown("---")
    st.subheader("📡 Oráculo de Mercado (Live)")
    precio_live = obtener_precio_mercado()
    st.metric(label="Bitcoin (BTC-USD) ahora", value=precio_live)
    
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# PESTAÑAS
tab1, tab2 = st.tabs(["🤖 Simulador de Negociación", "📊 Dashboard de Datos"])

with tab1:
    if "acuerdo_actual" not in st.session_state:
        st.session_state.acuerdo_actual = None

    if st.button("Iniciar Negociación Autónoma", use_container_width=True):
        st.info(f"🌐 Buscando precios reales de '{producto}' en internet...")
        info_web = buscar_precio_real(producto)
        st.success("¡Datos de mercado obtenidos! Iniciando agentes...")
        
        col1, col2 = st.columns(2)
        historial = [{"role": "user", "content": f"Hola, me interesa {producto}. Te ofrezco ${presupuesto_c - 30}."}]
        acuerdo, precio_final = False, 0
        
        with col1:
            st.subheader("💼 Vendedor")
            vendedor_placeholder = st.empty()
        with col2:
            st.subheader("🛒 Comprador")
            comprador_placeholder = st.empty()

        for turno in range(3):
            resp_v = chatear_con_agente("Vendedor", producto, precio_v, personalidad, historial, info_web)
            with vendedor_placeholder.container():
                st.chat_message("assistant", avatar="💼").write(resp_v)
            historial.append({"role": "assistant", "content": resp_v})
            
            if "acepto" in resp_v.lower() or "trato" in resp_v.lower():
                try: precio_final = float(re.findall(r'\d+', resp_v)[0])
                except: precio_final = precio_v
                acuerdo = True
                break
                
            resp_c = chatear_con_agente("Comprador", producto, presupuesto_c, personalidad, [{"role": "user", "content": f"El vendedor dijo: {resp_v}"}], info_web)
            with comprador_placeholder.container():
                st.chat_message("user", avatar="🛒").write(resp_c)
            historial.append({"role": "user", "content": resp_c})
            
            if "acepto" in resp_c.lower() or "trato" in resp_c.lower():
                try: precio_final = float(re.findall(r'\d+', resp_c)[0])
                except: precio_final = presupuesto_c
                acuerdo = True
                break

        if acuerdo:
            st.write("---")
            st.info("🛡️ Llamando al Agente Auditor (Escrow) para blindar la transacción...")
            resp_auditor = chatear_con_agente("Auditor", producto, precio_final, "Estricto", [], info_web)
            with st.chat_message("assistant", avatar="🛡️"):
                st.write(resp_auditor)
                
            if "Aprobado" in resp_auditor:
                st.session_state.acuerdo_actual = {"producto": producto, "precio": precio_final}
            else:
                st.error("❌ El Auditor rechazó el trato por riesgos legales.")
        else:
            st.error("❌ Las IAs no llegaron a un acuerdo.")

    # LÓGICA DE FIRMA DIGITAL HUMANA Y CONTRATO
    if st.session_state.acuerdo_actual is not None:
        st.warning("✍️ Se requiere autorización humana para ejecutar el pago y firmar el contrato.")
        
        if st.button("🔐 Firmar y Generar Contrato Legal", use_container_width=True, type="primary"):
            datos = st.session_state.acuerdo_actual
            texto_contrato = f"{datos['producto']}-{datos['precio']}-{time.time()}"
            hash_firma = hashlib.sha256(texto_contrato.encode()).hexdigest()
            
            # Guardamos en la nube de Supabase
            guardar_transaccion(datos['producto'], "BuyerBot", "SellerBot", datos['precio'], "COMPLETADO - FIRMADO", hash_firma[:15] + "...")
            
            st.success("✅ Contrato Firmado y guardado en la Nube (Supabase).")
            st.balloons()
            
            contrato_final = f"""
=========================================
CONTRATO DE COMERCIO AGÉNTICO B2B
=========================================
Producto: {datos['producto']}
Precio Final Acordado: ${datos['precio']}
Fecha: {time.strftime("%Y-%m-%d %H:%M:%S")}

FIRMA CRIPTOGRÁFICA (SHA-256):
{hash_firma}

Validez: Este documento certifica que los agentes autónomos 
y el Auditor de IA han verificado la transacción. 
=========================================
"""
            st.download_button(
                label="📄 Descargar Contrato (TXT)",
                data=contrato_final,
                file_name=f"Contrato_{datos['producto'].replace(' ', '_')}.txt",
                mime="text/plain"
            )
            
            st.session_state.acuerdo_actual = None

with tab2:
    st.subheader("📈 Historial de Transacciones (Ledger en la Nube)")
    df = obtener_transacciones()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte (CSV)", data=csv, file_name="reporte.csv", mime="text/csv")
        
        df_exitosas = df[df['estado'].str.contains('COMPLETADO', na=False)]
        if not df_exitosas.empty:
            fig = px.bar(df_exitosas, x='id', y='monto', color='producto', title="Precios de Cierre")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos aún en la nube.")
