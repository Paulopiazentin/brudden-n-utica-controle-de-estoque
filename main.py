import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date, timedelta
from io import BytesIO
from supabase import create_client

# ================= CONFIG =================
st.set_page_config("Gestão Caiaques", "🎣", layout="wide")

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.markdown("""
<style>
h1, h2, h3 { color:#0077b6; }
.stButton>button { width:100%; }
</style>
""", unsafe_allow_html=True)

# ================= UTIL =================
def hash_senha(s):
    return hashlib.sha256(str(s).encode()).hexdigest()

def df_excel(df):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        df.to_excel(w, index=False)
    return out.getvalue()

@st.cache_data
def carregar_dados():
    u = supabase.table("usuarios").select("*").execute().data
    e = supabase.table("estoque").select("*").execute().data
    m = supabase.table("movimentacoes").select("*").execute().data
    return pd.DataFrame(u), pd.DataFrame(e), pd.DataFrame(m)

def clear():
    st.cache_data.clear()

# ================= SESSÃO =================
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario_atual = ""
    st.session_state.perfil_atual = ""

# ================= LOGIN =================
def login(df_u):
    st.markdown("<h1 style='text-align: center;'>🔐 Controle de Estoque</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        with st.form("login"):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                user = df_u[df_u["usuario"] == u]
                if user.empty:
                    st.error("Usuário não encontrado")
                elif user.iloc[0]["senha"] != hash_senha(p):
                    st.error("Senha incorreta")
                else:
                    st.session_state.logado = True
                    st.session_state.usuario_atual = u
                    st.session_state.perfil_atual = user.iloc[0]["perfil"]
                    st.rerun()

# ================= DASHBOARD =================
def pagina_dashboard(df):
    st.title("📊 Dashboard de Estoque")
    df = df[df["status"] == "Ativo"]
    if df.empty:
        st.warning("Nenhum item ativo")
        return

    c1,c2,c3 = st.columns(3)
    c1.metric("📦 Total", int(df["quantidade"].sum()))
    crit = df[df["quantidade"] < df["estoque_minimo"]]
    c2.metric("⚠️ Críticos", len(crit))
    c3.metric("🏷️ Modelos", len(df))

    if not crit.empty:
        st.error("Itens abaixo do mínimo")
        st.dataframe(crit)

# ================= ESTOQUE =================
def pagina_estoque(df, perfil):
    st.title("📦 Gestão de Produtos")

    filtro = st.radio("Filtro:", ["Ativos","Inativos","Todos"], horizontal=True)
    if filtro=="Ativos": df=df[df["status"]=="Ativo"]
    if filtro=="Inativos": df=df[df["status"]=="Inativo"]

    st.dataframe(df, use_container_width=True)
    st.download_button("📥 Excel", df_excel(df), "estoque.xlsx")

    if perfil=="Admin":
        t1,t2 = st.tabs(["✨ Novo","⚙️ Editar"])

        with t1:
            with st.form("novo"):
                cod = st.text_input("Código")
                nome = st.text_input("Nome")
                cor = st.text_input("Cor")
                cat = st.text_input("Categoria")
                loc = st.text_input("Localização")
                min = st.number_input("Estoque mínimo",0)
                if st.form_submit_button("Cadastrar"):
                    supabase.table("estoque").insert({
                        "codigo":cod,"nome":nome,"cor":cor,
                        "categoria":cat,"localizacao":loc,
                        "quantidade":0,"estoque_minimo":min,"status":"Ativo"
                    }).execute()
                    clear(); st.rerun()

        with t2:
            cod = st.selectbox("Produto", df["codigo"])
            d = df[df["codigo"]==cod].iloc[0]
            with st.form("edit"):
                nome = st.text_input("Nome",d["nome"])
                stat = st.selectbox("Status",["Ativo","Inativo"],0 if d["status"]=="Ativo" else 1)
                if st.form_submit_button("Salvar"):
                    supabase.table("estoque").update({
                        "nome":nome,"status":stat
                    }).eq("codigo",cod).execute()
                    clear(); st.rerun()

# ================= MOV =================
def pagina_mov(df_e, df_m):
    st.title("🔄 Movimentações")
    ativos = df_e[df_e["status"]=="Ativo"]

    with st.form("mov"):
        prod = st.selectbox("Produto", ativos["codigo"])
        tipo = st.radio("Tipo",["Entrada","Saída"])
        qtd = st.number_input("Quantidade",1)
        obs = st.text_input("Obs")
        if st.form_submit_button("Confirmar"):
            item = ativos[ativos["codigo"]==prod].iloc[0]
            nova = item["quantidade"] + qtd if tipo=="Entrada" else item["quantidade"] - qtd
            if nova < 0:
                st.error("Estoque insuficiente"); return
            supabase.table("movimentacoes").insert({
                "usuario":st.session_state.usuario_atual,
                "codigo":prod,"tipo":tipo,
                "quantidade":qtd,"obs":obs,
                "data":datetime.now().isoformat()
            }).execute()
            supabase.table("estoque").update({"quantidade":nova}).eq("codigo",prod).execute()
            clear(); st.rerun()

    st.subheader("Histórico")
    if not df_m.empty:
        st.dataframe(df_m.sort_values("data",ascending=False))

# ================= USERS =================
def pagina_users(df):
    st.title("👥 Usuários")
    st.dataframe(df[["usuario","perfil"]])
    with st.form("user"):
        u = st.text_input("Login")
        s = st.text_input("Senha",type="password")
        p = st.selectbox("Perfil",["Admin","Gerente","Visualizador"])
        if st.form_submit_button("Criar"):
            supabase.table("usuarios").insert({
                "usuario":u,"senha":hash_senha(s),"perfil":p
            }).execute()
            clear(); st.rerun()

# ================= MAIN =================
df_u, df_e, df_m = carregar_dados()

if not st.session_state.logado:
    login(df_u)
else:
    with st.sidebar:
        st.title(f"👤 {st.session_state.usuario_atual}")
        menu = ["Dashboard","Estoque","Movimentações","Usuários","Sair"]
        if st.session_state.perfil_atual != "Admin":
            menu.remove("Usuários")
        op = st.radio("Menu",menu)

    if op=="Dashboard": pagina_dashboard(df_e)
    elif op=="Estoque": pagina_estoque(df_e, st.session_state.perfil_atual)
    elif op=="Movimentações": pagina_mov(df_e, df_m)
    elif op=="Usuários": pagina_users(df_u)
    else:
        st.session_state.logado=False
        st.rerun()

if __name__ == "__main__":

    main()
