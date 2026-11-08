import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from groq import Groq
import re
import time
import hashlib
from duckduckgo_search import DDGS
import yfinance as yf

# ==========================================
# 1. CONFIGURACIÓN Y CACHÉ DE CONEXIÓN
# ==========================================
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"].strip()
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

supabase = init_supabase()
client = Groq(api_key=st.secrets["GROQ_API_KEY"].strip())

# ==========================================
# 2. BASE DE DATOS (SUPABASE)
# ==========================================
def guardar_transaccion(producto, comprador, vendedor, monto, estado, hash_contrato):
    data = {
        "producto": producto, "comprador": comprador, "vendedor": vendedor, 
        "monto": monto, "estado": estado, "hash_contrato": hash_contrato
    }
    try:
        supabase.table("transacciones").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error en DB: {e}")
        return False

def actualizar_estado(id_transaccion, nuevo_estado):
    try:
        supabase.table("transacciones").update({"estado": nuevo_estado}).eq("id", id_transaccion).execute()
    except Exception as e:
        st.error(f"Error al actualizar: {e}")

def obtener_transacciones():
    try:
        res = supabase.table("transacciones").select("*").order("id", desc=True).execute()
        if res.data:
            return pd.DataFrame(res.data)
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. AGENTES DE IA
# ==========================================
def buscar_precio_real(producto):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"precio mayorista de {producto} NZD", max_results=2))
            if results: return results[0]['body']
    except: pass
    return "No hay datos exactos, usa tu instinto."

def agente_vendedor(nombre, producto, precio_min, personalidad, historial, info_web):
    prompt = f"Eres {nombre}, proveedor mayorista de {producto}. Precio mínimo: ${precio_min}. Personalidad: {personalidad}. Info mercado: {info_web}. SOLO discute el precio. Si aceptas, di exactamente: 'Acepto vender por $X'."
    chat = client.chat.completions.create(
        messages=[{"role": "system", "content": prompt}] + historial,
        model="openai/gpt-oss-20b", 
    )
    return chat.choices[0].message.content

def agente_comprador(producto, presupuesto, ofertas, info_web):
    prompt = f"Eres comprador B2B de {producto}. Presupuesto max: ${presupuesto}. Ofertas: {ofertas}. Info mercado: {info_web}. Elige la mejor oferta. Di exactamente: 'Acepto comprar a [Nombre] por $X'."
    chat = client.chat.completions.create(
        messages=[{"role": "system", "content": prompt}],
        model="openai/gpt-oss-20b", 
    )
    return chat.choices[0].message.content

# ==========================================
# 4. INTERFAZ WEB
# ==========================================
st.set_page_config(page_title="Agentic B2B", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&display=swap');
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-color: #050505; font-family: 'Space Grotesk', sans-serif; }
    h1 { background: -webkit-linear-gradient(45deg, #00ffcc, #0099ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 3rem !important; }
    .stButton>button { background: linear-gradient(90deg, #00ffcc 0%, #0099ff 100%) !important; color: #000 !important; font-weight: 800 !important; border-radius: 8px !important; border: none !important; }
    [data-testid="stChatMessage"] { background-color: #0a0a0a !important; border-left: 4px solid #00ffcc !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🏗️ Agentic B2B Negotiator")
st.markdown("Especialistas en Materiales de Construcción y Repuestos.")

# LOGIN
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.subheader("🔒 Acceso Cliente")
    passw = st.text_input("Contraseña (Usa: 1234)", type="password")
    if st.button("Ingresar"):
        if passw == "1234":
            st.session_state.autenticado = True
            st.rerun()
    st.stop()

# SIDEBAR
with st.sidebar:
    st.header("⚙️ Panel de Negociación")
    producto = st.selectbox("Producto a negociar:", ["Cemento y Acero", "Madera Estructural", "Repuestos de Autos", "Herramientas Eléctricas"])
    presupuesto = st.number_input("Presupuesto ($):", value=5000)
    
    st.markdown("---")
    st.subheader("📡 Mercado (Live)")
    try:
        st.metric("Bitcoin", f"${yf.Ticker('BTC-USD').history(period='1d')['Close'].iloc[-1]:,.2f}")
    except: pass

# TABS
tab1, tab2 = st.tabs(["🤝 Negociar", "📊 Panel del Dueño"])

with tab1:
    if st.button("Iniciar Negociación B2B", use_container_width=True):
        st.info(f"🌐 Buscando precios reales de '{producto}'...")
        info_web = buscar_precio_real(producto)
        
        col1, col2 = st.columns(2)
        oferta_inicial = presupuesto - 1000
        hist = [{"role": "user", "content": f"Necesito {producto}. Ofrezco ${oferta_inicial}."}]
        
        with col1:
            st.subheader("🏭 Proveedor A")
            with st.spinner('Negociando...'):
                resp_v1 = agente_vendedor("ProveedorA", producto, int(presupuesto * 0.6), "Agresivo y directo", hist, info_web)
            st.chat_message("assistant", avatar="🏭").write(resp_v1)
            
        with col2:
            st.subheader("🏭 Proveedor B")
            with st.spinner('Negociando...'):
                resp_v2 = agente_vendedor("ProveedorB", producto, int(presupuesto * 0.8), "Premium y formal", hist, info_web)
            st.chat_message("assistant", avatar="👑").write(resp_v2)
            
        st.info("🧠 Evaluando ofertas...")
        ofertas = f"A: {resp_v1} | B: {resp_v2}"
        resp_c = agente_comprador(producto, presupuesto, ofertas, info_web)
        
        with st.chat_message("user", avatar="🛒"):
            st.write(resp_c)
            
        if "Acepto comprar" in resp_c:
            try:
                precio_final = float(re.findall(r'\$(\d+)', resp_c)[0])
                v_elegido = "ProveedorA" if "A" in resp_c else "ProveedorB"
            except:
                precio_final = oferta_inicial
                v_elegido = "Proveedor Desconocido"
            st.session_state.acuerdo = {"prod": producto, "precio": precio_final, "vend": v_elegido}

    if "acuerdo" in st.session_state and st.session_state.acuerdo is not None:
        d = st.session_state.acuerdo
        st.success(f"✅ Trato negociado con {d['vend']} por ${d['precio']}.")
        hash_f = hashlib.sha256(f"{d['prod']}-{d['precio']}-{time.time()}".encode()).hexdigest()[:15]
        
        contrato_txt = f"CONTRATO B2B\nProducto: {d['prod']}\nProveedor: {d['vend']}\nMonto: ${d['precio']}\nHASH: {hash_f}"
        st.download_button("📄 Descargar Contrato", data=contrato_txt, file_name="contrato.txt")
        
        st.warning("⚠️ Para completar, transfiere a: **ASB Bank - 12-3456-7890123-00** (Concepto: Tu Nombre).")
        
        if st.button("✅ Marcar como Pagado (He hecho la transferencia)", type="primary", key="btn_pagar"):
            exito = guardar_transaccion(d['prod'], "ClienteNZ", d['vend'], d['precio'], "PENDIENTE DE PAGO", hash_f)
            if exito:
                st.success("¡Registrado! Tu pedido está en proceso.")
                st.session_state.acuerdo = None
                st.balloons()
                time.sleep(2)
                st.rerun()

with tab2:
    st.subheader("📊 Panel de Transacciones (Dueño)")
    df = obtener_transacciones()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        st.markdown("---")
        id_a_pagar = st.number_input("ID a marcar como PAGADA:", min_value=1, step=1)
        if st.button("Confirmar Pago Recibido"):
            actualizar_estado(id_a_pagar, "PAGADO")
            st.success(f"Transacción {id_a_pagar} actualizada.")
            st.rerun()
    else:
        st.info("Aún no hay transacciones.")
