import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da Página
st.set_page_config(
    page_title="Auditoria de Risco Cadastral e Compliance",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .main { background-color: #0e1117; color: #ffffff; }
        .block-container { padding-top: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CARREGAMENTO DE DADOS COM CAMINHO DINÂMICO E CACHE (@st.cache_data)
# -----------------------------------------------------------------------------
@st.cache_data
def carregar_dados():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    gold_dir = os.path.join(base_dir, "medallion", "gold")
    
    df_fato = pd.read_csv(os.path.join(gold_dir, "fato_fornecedores_auditoria.csv"))
    df_dim_forn = pd.read_csv(os.path.join(gold_dir, "dim_fornecedores.csv"))
    df_bridge = pd.read_csv(os.path.join(gold_dir, "bridge_fornecedores_cnae.csv"))
    df_cnae = pd.read_csv(os.path.join(gold_dir, "dim_cnae.csv"))
    df_cat = pd.read_csv(os.path.join(gold_dir, "dim_categoria_fornecimento.csv"))
    df_geo = pd.read_csv(os.path.join(gold_dir, "dim_geografia.csv"))
    df_sit = pd.read_csv(os.path.join(gold_dir, "dim_situacao_cadastral.csv"))
    
    return df_fato, df_dim_forn, df_bridge, df_cnae, df_cat, df_geo, df_sit

try:
    fato_fornecedores, dim_fornecedores, bridge_fornecedores_cnae, dim_cnae, dim_cat, dim_geo, dim_sit = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar os dados da camada Gold: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# UNIFICAÇÃO (MERGES) DO MODELO ESTRELA
# -----------------------------------------------------------------------------
df_master = pd.merge(fato_fornecedores, dim_fornecedores, on="ID_FORNECEDOR", how="left", suffixes=('', '_dim'))

# Merge com Situação Cadastral via SITUACAO_CADASTRAL
if 'SITUACAO_CADASTRAL' in df_master.columns and 'SITUACAO_CADASTRAL' in dim_sit.columns:
    df_master = pd.merge(df_master, dim_sit, on="SITUACAO_CADASTRAL", how="left")

# Merge com Geografia via MUNICIPIO_RFB para garantir o filtro de UF
if 'MUNICIPIO_RFB' in df_master.columns and 'MUNICIPIO_RFB' in dim_geo.columns:
    df_master = pd.merge(df_master, dim_geo, on="MUNICIPIO_RFB", how="left", suffixes=('', '_geo'))

if 'UF_RFB' not in df_master.columns:
    for col in df_master.columns:
        if 'UF' in col.upper():
            df_master['UF_RFB'] = df_master[col]
            break

# -----------------------------------------------------------------------------
# BARRA LATERAL DE FILTROS
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/combo-chart--v1.png", width=60)
st.sidebar.title("Filtros Executivos")
st.sidebar.markdown("---")

ufs_disponiveis = sorted(df_master['UF_RFB'].dropna().unique()) if 'UF_RFB' in df_master.columns else []
filtro_uf = st.sidebar.multiselect("Filtrar por UF", ufs_disponiveis)

categorias_disponiveis = sorted(df_master['CATEGORIA_FORNECIMENTO'].dropna().unique()) if 'CATEGORIA_FORNECIMENTO' in df_master.columns else []
filtro_categoria = st.sidebar.multiselect("Categoria de Fornecimento", categorias_disponiveis)

situacoes_disponiveis = sorted(df_master['DESCRICAO_SITUACAO'].dropna().unique()) if 'DESCRICAO_SITUACAO' in df_master.columns else []
filtro_situacao = st.sidebar.multiselect("Situação na Receita Federal", situacoes_disponiveis)

riscos_disponiveis = sorted(df_master['RISCO_CADASTRAL'].dropna().unique()) if 'RISCO_CADASTRAL' in df_master.columns else []
filtro_risco = st.sidebar.multiselect("Nível de Risco Cadastral", riscos_disponiveis)

df_filtrado = df_master.copy()
if filtro_uf and 'UF_RFB' in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado['UF_RFB'].isin(filtro_uf)]
if filtro_categoria and 'CATEGORIA_FORNECIMENTO' in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado['CATEGORIA_FORNECIMENTO'].isin(filtro_categoria)]
if filtro_situacao and 'DESCRICAO_SITUACAO' in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado['DESCRICAO_SITUACAO'].isin(filtro_situacao)]
if filtro_risco and 'RISCO_CADASTRAL' in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado['RISCO_CADASTRAL'].isin(filtro_risco)]

# -----------------------------------------------------------------------------
# NAVEGAÇÃO ENTRE ABAS
# -----------------------------------------------------------------------------
aba_selecionada = st.sidebar.radio(
    "Navegação do Relatório", 
    ["Estratégia", "Compliance", "Mercado", "Operacional"]
)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Dica:** Utilize a Central Operacional para extrair a lista filtrada de inconsistências em formato CSV.")

# =============================================================================
# TELA 1: ESTRATÉGIA
# =============================================================================
if aba_selecionada == "Estratégia":
    st.title("Auditoria de Risco Cadastral e Compliance")
    st.subheader("Exposição Financeira Executiva")
    st.markdown("---")

    total_forn = df_filtrado['ID_FORNECEDOR'].nunique() if 'ID_FORNECEDOR' in df_filtrado.columns else len(df_filtrado)
    reg_count = df_filtrado[df_filtrado['RISCO_CADASTRAL'] == 'Regular']['ID_FORNECEDOR'].nunique() if 'RISCO_CADASTRAL' in df_filtrado.columns else 0
    taxa_reg = (reg_count / total_forn) * 100 if total_forn > 0 else 0
    val_total = df_filtrado['VALOR_CONTRATADO_ANUAL'].sum() if 'VALOR_CONTRATADO_ANUAL' in df_filtrado.columns else 0
    val_risco = df_filtrado[df_filtrado['RISCO_CADASTRAL'].isin(['Critico', 'Critico (CNPJ Invalido)'])]['VALOR_CONTRATADO_ANUAL'].sum() if 'VALOR_CONTRATADO_ANUAL' in df_filtrado.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fornecedores Homologados", f"{total_forn:,}")
    col2.metric("Taxa de Regularidade RFB", f"{taxa_reg:.1f}%")
    col3.metric("Valor Total Contratado", f"R$ {val_total:,.0f}".replace(",", "."))
    col4.metric("Volume Financeiro em Risco", f"R$ {val_risco:,.0f}".replace(",", "."))

    st.markdown("<br>", unsafe_allow_html=True)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("##### Fornecedores por Situação RFB")
        if 'DESCRICAO_SITUACAO' in df_filtrado.columns:
            df_sit_plot = df_filtrado.groupby('DESCRICAO_SITUACAO')['ID_FORNECEDOR'].nunique().reset_index()
            df_sit_plot.columns = ['DESCRICAO_SITUACAO', 'Qtd_Fornecedores']
            
            fig_donut = px.pie(df_sit_plot, names='DESCRICAO_SITUACAO', values='Qtd_Fornecedores', hole=0.5,
                               color_discrete_sequence=px.colors.qualitative.Set2)
            fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_donut, use_container_width=True)

    with col_g2:
        st.markdown("##### Status de Homologação Interno vs Receita Federal")
        col_status_int = next((c for c in ['STATUS_HOMOLOGACAO', 'STATUS_HOMOLOGACAO_INTERNA'] if c in df_filtrado.columns), None)
        
        if col_status_int and 'DESCRICAO_SITUACAO' in df_filtrado.columns:
            df_stack = df_filtrado.groupby([col_status_int, 'DESCRICAO_SITUACAO'])['ID_FORNECEDOR'].nunique().reset_index()
            df_stack.columns = ['STATUS_HOMOLOGACAO', 'DESCRICAO_SITUACAO', 'Total_Fornecedores']
            
            fig_bar_stack = px.bar(df_stack, x='STATUS_HOMOLOGACAO', y='Total_Fornecedores', color='DESCRICAO_SITUACAO',
                                   barmode='stack', color_discrete_sequence=px.colors.qualitative.Safe)
            fig_bar_stack.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, xaxis_title="STATUS INTERNO de HOMOLOGACAO", yaxis_title="Total Fornecedores")
            st.plotly_chart(fig_bar_stack, use_container_width=True)

    st.markdown("##### Total Fornecedores por RISCO_CADASTRAL")
    if 'RISCO_CADASTRAL' in df_filtrado.columns:
        df_risco = df_filtrado.groupby('RISCO_CADASTRAL')['ID_FORNECEDOR'].nunique().reset_index().sort_values(by='ID_FORNECEDOR', ascending=True)
        fig_risco = px.bar(df_risco, x='ID_FORNECEDOR', y='RISCO_CADASTRAL', orientation='h',
                           text='ID_FORNECEDOR', color='RISCO_CADASTRAL',
                           color_discrete_map={'Alerta': '#f0ad4e', 'Critico': '#d9534f', 'Regular': '#5cb85c'})
        fig_risco.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250, showlegend=False)
        st.plotly_chart(fig_risco, use_container_width=True)

# =============================================================================
# TELA 2: COMPLIANCE (Auditoria de CNAE e Compatibilidade)
# =============================================================================
elif aba_selecionada == "Compliance":
    st.title("Auditoria de Risco Cadastral e Compliance")
    st.subheader("Auditoria de CNAE e Compatibilidade")
    st.markdown("---")

    total_forn = df_filtrado['ID_FORNECEDOR'].nunique()
    
    # Taxa de Regularidade CNAE (RISCO_CADASTRAL <> "Alerta")
    if 'RISCO_CADASTRAL' in df_filtrado.columns and total_forn > 0:
        qtd_regular = df_filtrado[df_filtrado['RISCO_CADASTRAL'] != 'Alerta']['ID_FORNECEDOR'].nunique()
        taxa_compat = (qtd_regular / total_forn) * 100
    else:
        taxa_compat = 0.0

    # Qtd CNAEs Principais Distintos (TIPO_CNAE == 'Principal')
    if 'TIPO_CNAE' in bridge_fornecedores_cnae.columns and 'CNAE_CODIGO' in bridge_fornecedores_cnae.columns:
        q_cnae_dist = bridge_fornecedores_cnae[bridge_fornecedores_cnae['TIPO_CNAE'].str.strip().str.capitalize() == 'Principal']['CNAE_CODIGO'].nunique()
    else:
        q_cnae_dist = dim_cnae['CNAE_CODIGO'].nunique() if 'CNAE_CODIGO' in dim_cnae.columns else 0

    # Volume CNAEs Secundários (filtrado estritamente por TIPO_CNAE == 'Secundário')
    if 'TIPO_CNAE' in bridge_fornecedores_cnae.columns:
        df_secundarios = bridge_fornecedores_cnae[bridge_fornecedores_cnae['TIPO_CNAE'].str.strip().str.capitalize() == 'Secundário']
        vol_secundarios = len(df_secundarios)
    else:
        vol_secundarios = len(bridge_fornecedores_cnae)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fornecedores Homologados", f"{total_forn:,}")
    col2.metric("Taxa Compatibilidade CNAE", f"{taxa_compat:.1f}%")
    col3.metric("Qtd CNAEs Principais Distintos", f"{q_cnae_dist:,}")
    col4.metric("Volume CNAEs Secundários", f"{vol_secundarios:,}")

    st.markdown("<br>", unsafe_allow_html=True)

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.markdown("##### Top 10 CNAEs Principais")
        if 'CNAE_PRINCIPAL_CODIGO' in df_filtrado.columns:
            top_cnae = df_filtrado['CNAE_PRINCIPAL_CODIGO'].value_counts().head(10).reset_index()
            top_cnae.columns = ['CNAE_CODIGO', 'Quantidade']
            fig_top = px.bar(top_cnae, x='Quantidade', y='CNAE_CODIGO', orientation='h', text='Quantidade',
                             color='Quantidade', color_continuous_scale='Purples')
            fig_top.update_layout(yaxis=dict(autorange="reversed"), margin=dict(t=10, b=10, l=10, r=10), height=350)
            st.plotly_chart(fig_top, use_container_width=True)

    with col_c2:
        st.markdown("##### CNAEs Secundários mais Comuns")
        if 'CNAE_CODIGO' in df_secundarios.columns:
            top_sec = df_secundarios['CNAE_CODIGO'].value_counts().head(15).reset_index()
            top_sec.columns = ['CNAE_CODIGO', 'Quantidade']
            top_sec['CNAE_CODIGO'] = top_sec['CNAE_CODIGO'].astype(str)
            fig_tree = px.treemap(top_sec, path=['CNAE_CODIGO'], values='Quantidade',
                                  color='Quantidade', color_continuous_scale='Blues')
            fig_tree.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350)
            st.plotly_chart(fig_tree, use_container_width=True)

    st.markdown("##### Amostra Detalhada de Conformidade")
    cols_exibir = [c for c in ['ID_FORNECEDOR', 'DESCRICAO_SITUACAO', 'RISCO_CADASTRAL', 'CNAE_COMPATIVEL'] if c in df_filtrado.columns]
    st.dataframe(df_filtrado[cols_exibir].head(10), use_container_width=True)

# =============================================================================
# TELA 3: MERCADO
# =============================================================================
elif aba_selecionada == "Mercado":
    st.title("Auditoria de Risco Cadastral e Compliance")
    st.subheader("Distribuição Geográfica & Grupos Económicos")
    st.markdown("---")

    col_m1, col_m2 = st.columns([1.2, 0.8])

    with col_m1:
        st.markdown("##### Volume de Fornecedores por UF")
        if 'UF_RFB' in df_filtrado.columns:
            df_uf = df_filtrado.groupby('UF_RFB')['ID_FORNECEDOR'].nunique().reset_index().sort_values(by='ID_FORNECEDOR', ascending=True)
            fig_uf = px.bar(df_uf, x='ID_FORNECEDOR', y='UF_RFB', orientation='h', text='ID_FORNECEDOR',
                            color='ID_FORNECEDOR', color_continuous_scale='Greens')
            fig_uf.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=400)
            st.plotly_chart(fig_uf, use_container_width=True)

    with col_m2:
        st.markdown("##### Volume de Filiais por CNPJ Raiz")
        if 'CNPJ_RAIZ' in df_filtrado.columns and 'MATRIZ_FILIAL' in df_filtrado.columns:
            df_filiais = df_filtrado[df_filtrado['MATRIZ_FILIAL'] == 'Filial']
            df_raiz_fil = df_filiais.groupby('CNPJ_RAIZ')['ID_FORNECEDOR'].count().reset_index()
            df_raiz_fil.columns = ['CNPJ Raiz', 'Número de Filiais Fornecedoras']
            st.dataframe(df_raiz_fil.sort_values(by='Número de Filiais Fornecedoras', ascending=False).head(8), use_container_width=True)

        st.markdown("##### Valor Faturado (Sede x Filial)")
        if 'MATRIZ_FILIAL' in df_filtrado.columns and 'VALOR_CONTRATADO_ANUAL' in df_filtrado.columns:
            df_matriz_filial = df_filtrado.groupby('MATRIZ_FILIAL')['VALOR_CONTRATADO_ANUAL'].sum().reset_index()
            fig_mf = px.pie(df_matriz_filial, names='MATRIZ_FILIAL', values='VALOR_CONTRATADO_ANUAL', hole=0.6,
                            color_discrete_sequence=['#512da8', '#03a9f4'])
            fig_mf.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250)
            st.plotly_chart(fig_mf, use_container_width=True)

# =============================================================================
# TELA 4: OPERACIONAL
# =============================================================================
elif aba_selecionada == "Operacional":
    st.title("Auditoria de Risco Cadastral e Compliance")
    st.subheader("Central de Ação & Bloqueio Operacional")
    st.markdown("---")

    col_s1, col_s2, col_s3 = st.columns(3)
    pesquisa_razao = col_s1.text_input("Pesquisar por Razão Social")
    pesquisa_cnpj = col_s2.text_input("Pesquisar por CNPJ")
    pesquisa_id = col_s3.text_input("Pesquisar por ID Fornecedor")

    df_operacional = df_filtrado.copy()

    if pesquisa_razao and 'RAZAO_SOCIAL' in df_operacional.columns:
        df_operacional = df_operacional[df_operacional['RAZAO_SOCIAL'].str.contains(pesquisa_razao, case=False, na=False)]
    if pesquisa_cnpj and 'CNPJ_LIMPO' in df_operacional.columns:
        df_operacional = df_operacional[df_operacional['CNPJ_LIMPO'].str.contains(pesquisa_cnpj, case=False, na=False)]
    if pesquisa_id and 'ID_FORNECEDOR' in df_operacional.columns:
        df_operacional = df_operacional[df_operacional['ID_FORNECEDOR'].str.contains(pesquisa_id, case=False, na=False)]

    colunas_tabela = [c for c in [
        'ID_FORNECEDOR', 'CNPJ_LIMPO', 'RAZAO_SOCIAL', 'CATEGORIA_FORNECIMENTO', 
        'MATRIZ_FILIAL', 'STATUS_HOMOLOGACAO', 'UF_RFB', 'MUNICIPIO_RFB', 'RISCO_CADASTRAL'
    ] if c in df_operacional.columns]

    st.markdown(f"**Registos encontrados para ação:** {len(df_operacional)}")
    st.dataframe(df_operacional[colunas_tabela], use_container_width=True, height=450)

    st.markdown("---")
    st.markdown("#### Exportação de Inconsistências")
    
    csv_export = df_operacional.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descarregar Lista Filtrada de Inconsistências (.csv)",
        data=csv_export,
        file_name="inconsistencias_auditoria_fornecedores.csv",
        mime="text/csv",
        help="Clica para exportar os dados filtrados atuais em formato CSV para tratamento operacional."
    )