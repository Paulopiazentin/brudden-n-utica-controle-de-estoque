import streamlit as st
import pandas as pd
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, date, timedelta
from io import BytesIO


# --- CONFIGURAÇÃO DE CAMINHOS (IMPORTANTE PARA EXECUTÁVEL E REDE) ---
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_path()
DB_PATH = os.path.join(BASE_DIR, "dados_sistema.db")

# --- CONFIGURAÇÃO DA PÁGINA (MANTIDO) ---
st.set_page_config(page_title="Gestão Caiaques", layout="wide", page_icon="🎣")

st.markdown("""
    <style>
    h1, h2, h3 { color: #0077b6; }
    .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)


# --- FUNÇÕES DE UTILIDADE E SEGURANÇA (MANTIDO) ---
def hash_senha(senha):
    return hashlib.sha256(str(senha).encode()).hexdigest()


# --- NOVA LÓGICA DE BANCO DE DADOS (SUBSTITUINDO CSV) ---

def init_db():
    """Garante que as tabelas existam no banco SQLite com a mesma estrutura dos seus CSVs"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Tabela de Usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (usuario TEXT PRIMARY KEY, senha TEXT, perfil TEXT)''')

    # Tabela de Estoque
    c.execute('''CREATE TABLE IF NOT EXISTS estoque 
                 (Codigo TEXT PRIMARY KEY, Nome TEXT, Cor TEXT, Categoria TEXT, 
                  Quantidade INTEGER, Estoque_Minimo INTEGER, Localizacao TEXT, Status TEXT)''')

    # Tabela de Movimentações
    c.execute('''CREATE TABLE IF NOT EXISTS movimentacoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, Data TEXT, Usuario TEXT, 
                  Codigo TEXT, Tipo TEXT, Quantidade INTEGER, Obs TEXT)''')

    # Se for a primeira vez, cria usuários padrão
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        usuarios_iniciais = [
            ('admin', hash_senha('admin123'), 'Admin'),
            ('gerente', hash_senha('1234'), 'Gerente'),
            ('visitante', hash_senha('1234'), 'Visualizador')
        ]
        c.executemany("INSERT INTO usuarios VALUES (?, ?, ?)", usuarios_iniciais)

    conn.commit()
    conn.close()


def carregar_dados():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    df_u = pd.read_sql_query("SELECT * FROM usuarios", conn)
    df_e = pd.read_sql_query("SELECT * FROM estoque", conn)
    df_m = pd.read_sql_query("SELECT * FROM movimentacoes", conn)
    conn.close()
    return df_u, df_e, df_m


def salvar_dados(df, tabela):
    """Salva o DataFrame na tabela correspondente do SQLite"""
    conn = sqlite3.connect(DB_PATH)
    # No seu código original, você concatenava e salvava o arquivo inteiro.
    # O comando 'replace' aqui faz exatamente o mesmo: atualiza a tabela com o novo estado do DF.
    df.to_sql(tabela, conn, if_exists='replace', index=False)
    conn.commit()
    conn.close()


# --- FUNÇÕES DE EXCEL (MANTIDO) ---
def converter_df_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
        workbook = writer.book
        worksheet = writer.sheets['Dados']
        header_format = workbook.add_format(
            {'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1})
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(str(col))) + 2
            worksheet.set_column(i, i, max_len)
            worksheet.write(0, i, col, header_format)
    return output.getvalue()


# --- GESTÃO DE SESSÃO (MANTIDO) ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario_atual'] = ''
    st.session_state['perfil_atual'] = ''


def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Controle de Estoque</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            user = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar")
            if submit:
                df_users, _, _ = carregar_dados()
                usuario_encontrado = df_users[df_users['usuario'] == user]
                if not usuario_encontrado.empty:
                    if usuario_encontrado.iloc[0]['senha'] == hash_senha(password):
                        st.session_state['logado'] = True
                        st.session_state['usuario_atual'] = user
                        st.session_state['perfil_atual'] = usuario_encontrado.iloc[0]['perfil']
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não encontrado.")


def logout():
    st.session_state['logado'] = False
    st.rerun()


# --- PÁGINAS (ESTRUTURA E FUNCIONALIDADES 100% MANTIDAS) ---

def pagina_dashboard(df_estoque, df_mov):
    st.title("📊 Dashboard de Estoque")
    df_estoque = df_estoque[df_estoque['Status'] == 'Ativo']
    if df_estoque.empty:
        st.warning("Não há produtos ATIVOS para exibir no Dashboard.")
        return
    st.subheader("Filtros de Visualização (Apenas Ativos)")
    col_f1, col_f2 = st.columns(2)
    lista_nomes = sorted(df_estoque['Nome'].unique())
    lista_cores = sorted(df_estoque['Cor'].unique())
    filtro_nome = col_f1.multiselect("Filtrar por Nome", lista_nomes)
    filtro_cor = col_f2.multiselect("Filtrar por Cor", lista_cores)
    df_filtered = df_estoque.copy()
    if filtro_nome: df_filtered = df_filtered[df_filtered['Nome'].isin(filtro_nome)]
    if filtro_cor: df_filtered = df_filtered[df_filtered['Cor'].isin(filtro_cor)]
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("📦 Total de Peças", f"{int(df_filtered['Quantidade'].sum())}")
    itens_criticos = df_estoque[df_estoque['Quantidade'] < df_estoque['Estoque_Minimo']].shape[0]
    c2.metric("⚠️ Itens Críticos", f"{itens_criticos}", delta_color="inverse")
    c3.metric("🏷️ Modelos Ativos", df_filtered.shape[0])
    if itens_criticos > 0:
        st.markdown("---")
        st.error(f"🚨 Alerta: Itens abaixo do mínimo.")
        st.dataframe(df_estoque[df_estoque['Quantidade'] < df_estoque['Estoque_Minimo']], use_container_width=True)


def pagina_estoque(df_estoque, perfil):
    st.title("📦 Gestão de Produtos")
    status_ver = st.radio("Mostrar produtos:", ["Apenas Ativos", "Apenas Inativos (Fora de Linha)", "Todos"],
                          horizontal=True)
    df_view = df_estoque.copy()
    if status_ver == "Apenas Ativos":
        df_view = df_view[df_view['Status'] == 'Ativo']
    elif status_ver == "Apenas Inativos (Fora de Linha)":
        df_view = df_view[df_view['Status'] == 'Inativo']
    st.dataframe(df_view, use_container_width=True)
    if not df_view.empty:
        try:
            excel_data = converter_df_para_excel(df_view)
            st.download_button(label="📥 Baixar Lista em Excel", data=excel_data, file_name="estoque.xlsx",
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except:
            pass
    st.markdown("---")
    if perfil == 'Admin':
        tab_cad, tab_edit = st.tabs(["✨ Cadastrar Novo Item", "⚙️ Editar ou Inativar Item"])
        with tab_cad:
            with st.form("form_novo_item", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                cod_novo = c1.text_input("Código (ID Único)")
                nom_novo = c2.text_input("Nome")
                cor_novo = c3.text_input("Cor")
                c4, c5, c6 = st.columns(3)
                cat_novo = c4.text_input("Categoria")
                loc_novo = c5.text_input("Localização")
                min_novo = c6.number_input("Estoque Mínimo", min_value=0, value=5)
                if st.form_submit_button("Finalizar Cadastro"):
                    cod_novo = str(cod_novo).strip()
                    if not cod_novo:
                        st.error("Código é obrigatório.")
                    elif cod_novo in df_estoque['Codigo'].values:
                        st.error("Este código já existe!")
                    else:
                        novo = pd.DataFrame(
                            [{'Codigo': cod_novo, 'Nome': nom_novo, 'Cor': cor_novo, 'Categoria': cat_novo,
                              'Quantidade': 0, 'Estoque_Minimo': min_novo, 'Localizacao': loc_novo, 'Status': 'Ativo'}])
                        df_estoque = pd.concat([df_estoque, novo], ignore_index=True)
                        salvar_dados(df_estoque, 'estoque')  # Salva no SQL
                        st.success(f"Item {cod_novo} cadastrado!")
                        st.rerun()
        with tab_edit:
            opcoes_editar = df_estoque.apply(lambda x: f"{x['Codigo']} - {x['Nome']} ({x['Cor']})", axis=1)
            item_para_editar = st.selectbox("Selecione o produto para alterar", options=opcoes_editar)
            if item_para_editar:
                cod_edit = item_para_editar.split(" - ")[0].strip()
                dados_atuais = df_estoque[df_estoque['Codigo'] == cod_edit].iloc[0]
                with st.form("form_edicao_item"):
                    c1, c2, c_stat = st.columns([2, 1, 1])
                    nom_edit = c1.text_input("Nome", value=dados_atuais['Nome'])
                    cor_edit = c2.text_input("Cor", value=dados_atuais['Cor'])
                    stat_edit = c_stat.selectbox("Status", ["Ativo", "Inativo"],
                                                 index=0 if dados_atuais['Status'] == 'Ativo' else 1)
                    c4, c5, c6 = st.columns(3)
                    cat_edit = c4.text_input("Categoria", value=dados_atuais['Categoria'])
                    loc_edit = c5.text_input("Localização", value=dados_atuais['Localizacao'])
                    min_edit = c6.number_input("Estoque Mínimo", min_value=0, value=int(dados_atuais['Estoque_Minimo']))
                    if st.form_submit_button("Salvar Alterações"):
                        idx = df_estoque[df_estoque['Codigo'] == cod_edit].index[0]
                        df_estoque.loc[idx, ['Nome', 'Cor', 'Categoria', 'Localizacao', 'Estoque_Minimo', 'Status']] = [
                            nom_edit, cor_edit, cat_edit, loc_edit, min_edit, stat_edit]
                        salvar_dados(df_estoque, 'estoque')  # Salva no SQL
                        st.success(f"Item {cod_edit} atualizado!")
                        st.rerun()
    else:
        st.info("💡 Apenas usuários com perfil **Admin** podem cadastrar ou editar.")


def pagina_movimentacao(df_estoque, df_mov, usuario):
    st.title("🔄 Entrada e Saída")
    df_ativos = df_estoque[df_estoque['Status'] == 'Ativo']
    if df_ativos.empty:
        st.warning("Não há produtos ATIVOS.")
        return
    c_left, c_right = st.columns([1, 2])
    with c_left:
        with st.form("form_mov"):
            opcoes = df_ativos.apply(lambda x: f"{x['Codigo']} - {x['Nome']} ({x['Cor']})", axis=1)
            sel_display = st.selectbox("Selecione o Item", options=opcoes)
            tipo = st.radio("Tipo", ["Entrada (+)", "Saída (-)"], horizontal=True)
            qtd = st.number_input("Quantidade", min_value=1, step=1)
            obs = st.text_area("Observação")
            if st.form_submit_button("Confirmar"):
                cod_sel = sel_display.split(" - ")[0].strip()
                idx = df_estoque[df_estoque['Codigo'] == cod_sel].index[0]
                if tipo == "Saída (-)" and df_estoque.at[idx, 'Quantidade'] < qtd:
                    st.error("Estoque insuficiente!")
                else:
                    df_estoque.at[idx, 'Quantidade'] += qtd if "Entrada" in tipo else -qtd
                    nova_mov = pd.DataFrame(
                        [{'Data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Usuario': usuario, 'Codigo': cod_sel,
                          'Tipo': tipo.split()[0], 'Quantidade': qtd, 'Obs': obs}])
                    df_mov = pd.concat([df_mov, nova_mov], ignore_index=True)
                    salvar_dados(df_estoque, 'estoque')
                    salvar_dados(df_mov, 'movimentacoes')
                    st.success("Registrado!")
                    st.rerun()
    with c_right:
        if not df_mov.empty:
            df_mov['Data_dt'] = pd.to_datetime(df_mov['Data']).dt.date
            with st.expander("Filtros"):
                d1, d2 = st.columns(2)
                inicio, fim = d1.date_input("Início", date.today() - timedelta(days=30)), d2.date_input("Fim",
                                                                                                        date.today())
                f_user = st.multiselect("Usuário", df_mov['Usuario'].unique())
            df_m_f = df_mov[(df_mov['Data_dt'] >= inicio) & (df_mov['Data_dt'] <= fim)]
            if f_user: df_m_f = df_m_f[df_m_f['Usuario'].isin(f_user)]
            st.dataframe(df_m_f.drop(columns=['Data_dt']).sort_values(by='Data', ascending=False),
                         use_container_width=True)


def pagina_admin_usuarios(df_users):
    st.title("👥 Usuários (Admin)")
    c1, c2 = st.columns(2)
    with c1:
        st.dataframe(df_users[['usuario', 'perfil']], use_container_width=True)
    with c2:
        with st.form("novo_user"):
            u, p = st.text_input("Login"), st.text_input("Senha", type="password")
            pf = st.selectbox("Perfil", ["Admin", "Gerente", "Visualizador"])
            if st.form_submit_button("Criar"):
                if u in df_users['usuario'].values:
                    st.error("Existe!")
                else:
                    df_users = pd.concat(
                        [df_users, pd.DataFrame([{'usuario': u, 'senha': hash_senha(p), 'perfil': pf}])],
                        ignore_index=True)
                    salvar_dados(df_users, 'usuarios')
                    st.success("Usuário criado!")
                    st.rerun()


# --- MAIN ---
def main():
    df_u, df_e, df_m = carregar_dados()
    if not st.session_state['logado']:
        login()
    else:
        user, role = st.session_state['usuario_atual'], st.session_state['perfil_atual']
        with st.sidebar:
            st.title(f"👤 {user}")
            # Ajuste automático do caminho da logo
            logo_path = os.path.join(BASE_DIR, "logo.png")
            if os.path.exists(logo_path):
                st.image(logo_path, use_container_width=True)
            else:
                st.markdown("### 🛶 Sua Empresa")
            st.info(f"Perfil: {role}")
            st.markdown("---")
            menu = ["Dashboard", "Estoque", "Sair"]
            if role in ["Admin", "Gerente"]: menu.insert(2, "Movimentações")
            if role == "Admin": menu.insert(3, "Usuários")
            choice = st.sidebar.radio("Menu", menu)

        if choice == "Dashboard":
            pagina_dashboard(df_e, df_m)
        elif choice == "Estoque":
            pagina_estoque(df_e, role)
        elif choice == "Movimentações":
            pagina_movimentacao(df_e, df_m, user)
        elif choice == "Usuários":
            pagina_admin_usuarios(df_u)
        elif choice == "Sair":
            logout()


if __name__ == "__main__":
    main()