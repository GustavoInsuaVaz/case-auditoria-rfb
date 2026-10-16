# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import os
from pathlib import Path

st.set_page_config(
    page_title="Portal de Compliance & Risco - Auditoria de Fornecedores",
    page_icon="🛡️",
    layout="wide"
)

# Diretórios e caminhos dos dados da Camada Gold
GOLD_DIR = Path(__file__).resolve().parent / "medallion" / "gold"
GOLD_DIR = "/content/drive/MyDrive/Curriculo/Processos_Seletivos/Case_ABR_GUSTAVO_VAZ_2026/medallion/gold"
print(f"caminho: {GOLD_DIR}")
FATO_PATH = os.path.join(GOLD_DIR, 'fato_fornecedores_auditoria.csv')
print(f"tamanho fato: {len()}")
FORN_PATH = os.path.join(GOLD_DIR, 'dim_fornecedores.csv')
CNAE_PATH = os.path.join(GOLD_DIR, 'dim_cnae.csv')
BRIDGE_PATH = os.path.join(GOLD_DIR, 'bridge_fornecedores_cnae.csv')

@st.cache_data
def carregar_dados_completos():
    if not os.path.exists(FATO_PATH) or not os.path.exists(FORN_PATH):
        return None, None, None, None

    df_fato = pd.read_csv(FATO_PATH)
    df_forn = pd.read_csv(FORN_PATH)
    df_cnae = pd.read_csv(CNAE_PATH) if os.path.exists(CNAE_PATH) else pd.DataFrame(columns=['CNAE_CODIGO', 'CNAE_DESCRICAO'])
    df_bridge = pd.read_csv(BRIDGE_PATH) if os.path.exists(BRIDGE_PATH) else pd.DataFrame(columns=['ID_FORNECEDOR', 'CNPJ_LIMPO', 'CNAE_CODIGO'])

    # Garantindo colunas essenciais na Fato
    if 'VALOR_CONTRATADO_ANUAL' not in df_fato.columns:
        df_fato['VALOR_CONTRATO'] = 0.0
    df_fato['VALOR_CONTRATO'] = df_fato['VALOR_CONTRATO'].fillna(0.0)

    if 'CATEGORIA' not in df_fato.columns:
        df_fato['CATEGORIA'] = 'Não Especificado'
    df_fato['CATEGORIA'] = df_fato['CATEGORIA'].fillna('Não Especificado')

    if 'SITUACAO_FORNECEDOR' not in df_fato.columns:
        df_fato['SITUACAO_FORNECEDOR'] = 'Ativo'
    df_fato['SITUACAO_FORNECEDOR'] = df_fato['SITUACAO_FORNECEDOR'].fillna('Ativo')

    if 'RISCO_CADASTRAL' not in df_fato.columns:
        df_fato['RISCO_CADASTRAL'] = 'Regular'
    df_fato['RISCO_CADASTRAL'] = df_fato['RISCO_CADASTRAL'].fillna('Regular')

    # Unificando Fato e Dimensões
    df_forn_clean = df_forn.drop_duplicates(subset=['ID_FORNECEDOR', 'CNPJ_LIMPO'])
    cols_to_use = [c for c in df_forn_clean.columns if c not in ['CATEGORIA', 'VALOR_CONTRATO', 'SITUACAO_FORNECEDOR', 'DATA_HOMOLOGACAO', 'CNPJ_VALIDO', 'RISCO_CADASTRAL'] or c in ['ID_FORNECEDOR', 'CNPJ_LIMPO']]
    df_merged = pd.merge(df_fato, df_forn_clean[cols_to_use], on=['ID_FORNECEDOR', 'CNPJ_LIMPO'], how='left')

    # Tratamento agressivo e seguro contra valores nulos nas dimensões mapeadas no painel
    mapeamento_nulos = {
        'SITUACAO_CADASTRAL': 'Sem Consulta RFB',
        'DESCRICAO_SITUACAO': 'SEM INFORMAÇÃO RFB',
        'UF_RFB': 'Não Informado',
        'MUNICIPIO_RFB': 'Não Informado',
        'MATRIZ_FILIAL': 'Não Informado',
        'CNPJ_RAIZ': 'Não Informado',
        'RAZAO_SOCIAL_INFORMADA': 'Razão Social não Encontrada',
        'CNAE_PRINCIPAL_DESCRICAO': 'Sem Descrição Econômica'
    }
    for col, val in mapeamento_nulos.items():
        if col in df_merged.columns:
            df_merged[col] = df_merged[col].fillna(val).astype(str).str.strip()
            df_merged[col] = df_merged[col].replace({'': val, 'nan': val, 'NaN': val})
        else:
            df_merged[col] = val

    return df_merged, df_fato, df_cnae, df_bridge

df_painel, df_fato_raw, df_cnae_raw, df_bridge_raw = carregar_dados_completos()

if df_painel is None:
    st.error("⚠️ Tabelas da camada Gold não encontradas. Certifique-se de executar o pipeline de dados primeiro!")
else: 
    # -------------------------------------------------------------------------
    # BARRA LATERAL - FILTROS MULTIPLOS
    # -------------------------------------------------------------------------
    st.sidebar.header("🔍 Filtros de Auditoria")

    # Filtro por UF
    ufs_disponiveis = ['Todos'] + sorted(list(df_painel['UF_RFB'].dropna().unique()))
    uf_sel = st.sidebar.selectbox("Estado (UF RFB):", ufs_disponiveis)

    # Filtro por Categoria
    categorias_disponiveis = ['Todas'] + sorted(list(df_painel['CATEGORIA'].dropna().unique()))
    cat_sel = st.sidebar.selectbox("Categoria de Serviço:", categorias_disponiveis)

    # Filtro por Situação Cadastral
    situacoes_disponiveis = ['Todas'] + sorted(list(df_painel['DESCRICAO_SITUACAO'].dropna().unique()))
    situacao_sel = st.sidebar.selectbox("Situação Cadastral RFB:", situacoes_disponiveis)

    # Filtro por Nível de Risco
    riscos_disponiveis = ['Todos'] + sorted(list(df_painel['RISCO_CADASTRAL'].dropna().unique()))
    risco_sel = st.sidebar.selectbox("Nível de Risco Cadastral:", riscos_disponiveis)

    # Aplicando Filtros reativos
    df_filtrado = df_painel.copy()
    if uf_sel != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['UF_RFB'] == uf_sel]
    if cat_sel != 'Todas':
        df_filtrado = df_filtrado[df_filtrado['CATEGORIA'] == cat_sel]
    if situacao_sel != 'Todas':
        df_filtrado = df_filtrado[df_filtrado['DESCRICAO_SITUACAO'] == situacao_sel]
    if risco_sel != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['RISCO_CADASTRAL'] == risco_sel]

    # Título Principal
    st.title("🛡️ Portal de Compliance & Risco Cadastral B2B")
    st.markdown("Painel unificado para monitoramento de integridade e saneamento de dados de fornecedores.")

    # Navegação por Abas
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Visão 1: Painel Executivo",
        "🔬 Visão 2: Auditoria de CNAEs",
        "🗺️ Visão 3: Geografia e Grupos",
        "🚨 Visão 4: Central de Bloqueio"
    ])

    # -------------------------------------------------------------------------
    # VISÃO 1: PAINEL EXECUTIVO
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("Painel Executivo e Exposição Financeira Estratégica")

        k1, k2, k3, k4 = st.columns(4)
        total_forn = len(df_filtrado)
        total_val_contratos = float(df_filtrado['VALOR_CONTRATO'].sum())
        taxa_regularidade = float((df_filtrado['RISCO_CADASTRAL'] == 'Regular').mean() * 100) if total_forn > 0 else 100.0
        volume_critico = float(df_filtrado[df_filtrado['RISCO_CADASTRAL'] != 'Regular']['VALOR_CONTRATO'].sum())

        k1.metric("Total de Fornecedores", f"{total_forn:,}")
        k2.metric("Volume Total Contratado", f"R$ {total_val_contratos:,.2f}")
        k3.metric("Taxa de Regularidade", f"{taxa_regularidade:.2f}%")
        k4.metric("Volume Crítico Financeiro", f"R$ {volume_critico:,.2f}")

        st.markdown("---")

        col_pie, col_matrix = st.columns(2)
        with col_pie:
            st.markdown("#### Distribuição de Situação Cadastral RFB")
            if total_forn > 0:
                fig_situacao = px.pie(
                    df_filtrado,
                    names='DESCRICAO_SITUACAO',
                    title="Composição de Situações Oficiais na Base Filtrada",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                st.plotly_chart(fig_situacao, width='stretch')
            else:
                st.info("Nenhum fornecedor disponível com os filtros atuais para gerar gráficos.")

        with col_matrix:
            st.markdown("#### Matriz de Auditoria Cadastral")
            if total_forn > 0:
                df_matrix = df_filtrado.groupby(['SITUACAO_FORNECEDOR', 'DESCRICAO_SITUACAO']).size().reset_index(name='Quantidade')
                fig_heatmap = px.bar(
                    df_matrix,
                    x='DESCRICAO_SITUACAO',
                    y='Quantidade',
                    color='SITUACAO_FORNECEDOR',
                    title="Cruzamento: Homologação Interna vs Situação Cadastral Receita Federal",
                    barmode='stack'
                )
                st.plotly_chart(fig_heatmap, width='stretch')
            else:
                st.info("Sem dados para a matriz.")

    # -------------------------------------------------------------------------
    # VISÃO 2: AUDITORIA DE CNAE
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("Auditoria de Compatibilidade de CNAEs")

        col_cnae_p, col_cnae_s = st.columns(2)
        with col_cnae_p:
            st.markdown("#### Top 10 CNAEs Principais por Volume")
            df_com_cnae = df_filtrado[df_filtrado['CNAE_PRINCIPAL_DESCRICAO'] != 'Sem Descrição Econômica']
            if not df_com_cnae.empty:
                top_cnae = df_com_cnae['CNAE_PRINCIPAL_DESCRICAO'].value_counts().head(10).reset_index()
                top_cnae.columns = ['Descrição CNAE', 'Quantidade']
                fig_cnae = px.bar(
                    top_cnae,
                    y='Descrição CNAE',
                    x='Quantidade',
                    orientation='h',
                    title="Volume de Fornecedores por Atividade Principal"
                )
                fig_cnae.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_cnae, width='stretch')
            else:
                st.info("Atividade econômica (CNAE) principal não foi mapeada via API para a amostra filtrada.")

        with col_cnae_s:
            st.markdown("#### Distribuição de CNAEs Secundários")
            if df_bridge_raw is not None and not df_bridge_raw.empty:
                df_bridge_filtered = df_bridge_raw[df_bridge_raw['ID_FORNECEDOR'].isin(df_filtrado['ID_FORNECEDOR'])]
                if not df_bridge_filtered.empty:
                    sec_counts = df_bridge_filtered['CNAE_CODIGO'].value_counts().head(10).reset_index()
                    sec_counts.columns = ['Código CNAE', 'Frequência']
                    fig_sec = px.bar(
                        sec_counts,
                        x='Código CNAE',
                        y='Frequência',
                        title="CNAEs Secundários mais Declarados (Tabela Bridge)",
                        color_discrete_sequence=['#9b59b6']
                    )
                    st.plotly_chart(fig_sec, width='stretch')
                else:
                    st.info("Nenhum CNAE secundário associado à amostra filtrada.")
            else:
                st.info("Tabela bridge de CNAEs não contém dados cadastrados.")

    # -------------------------------------------------------------------------
    # VISÃO 3: DISTRIBUIÇÃO GEOGRÁFICA
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("Geografia e Estrutura de Grupos Econômicos")

        col_map, col_grupos = st.columns(2)
        with col_map:
            st.markdown("#### Concentração de Fornecedores por Estado (UF)")
            df_uf = df_filtrado.groupby('UF_RFB').agg(
                Volume=('ID_FORNECEDOR', 'count'),
                Taxa_Irregularidade=('RISCO_CADASTRAL', lambda x: (x != 'Regular').mean() * 100)
            ).reset_index()

            fig_uf = px.bar(
                df_uf,
                x='UF_RFB',
                y='Volume',
                color='Taxa_Irregularidade',
                title="Volumetria por UF e Taxa de Irregularidade (%)",
                color_continuous_scale='Reds'
            )
            st.plotly_chart(fig_uf, width='stretch')

        with col_grupos:
            st.markdown("#### Análise de Concentração (CNPJ Raiz / Grupos)")
            df_grupos_validos = df_filtrado[df_filtrado['CNPJ_RAIZ'] != 'Não Informado']
            if not df_grupos_validos.empty:
                grupos = df_grupos_validos.groupby('CNPJ_RAIZ').size().reset_index(name='Filiais_Contratadas')
                grupos = grupos.sort_values(by='Filiais_Contratadas', ascending=False).head(10)

                fig_grupos = px.bar(
                    grupos,
                    x='CNPJ_RAIZ',
                    y='Filiais_Contratadas',
                    title="Maiores Grupos Econômicos por Volume de Filiais",
                    labels={'CNPJ_RAIZ': 'CNPJ Raiz Grupo'},
                    color_discrete_sequence=['#e67e22']
                )
                st.plotly_chart(fig_grupos, width='stretch')
            else:
                st.info("Sem informações de CNPJ Raiz para agrupar filiais.")

        st.markdown("---")
        st.markdown("#### Proporção do Volume Contratado: Matriz vs Filiais")
        fig_matriz_filial = px.box(
            df_filtrado,
            x='MATRIZ_FILIAL',
            y='VALOR_CONTRATO',
            color='MATRIZ_FILIAL',
            title="Distribuição de Valor de Contratos por Classificação Estabelecimento"
        )
        st.plotly_chart(fig_matriz_filial, width='stretch')

    # -------------------------------------------------------------------------
    # VISÃO 4: CENTRAL DE BLOQUEIO
    # -------------------------------------------------------------------------
    with tab4:
        st.subheader("Central de Bloqueio Preventivo e Auditoria Operacional")
        st.markdown("Lista de fornecedores que requerem intervenção imediata devido a inconsistências cadastrais.")

        # Filtramos as anomalias
        df_anomalias = df_filtrado[
            (df_filtrado['RISCO_CADASTRAL'] != 'Regular') |
            (~df_filtrado['DESCRICAO_SITUACAO'].isin(['ATIVA', 'ATIVA ', 'SEM INFORMAÇÃO RFB']))
        ]

        busca = st.text_input("🔎 Busca rápida (Digite o Nome do Fornecedor ou CNPJ):", "")
        if busca:
            df_anomalias = df_anomalias[
                df_anomalias['RAZAO_SOCIAL_INFORMADA'].str.contains(busca, case=False, na=False) |
                df_anomalias['CNPJ_LIMPO'].str.contains(busca, na=False)
            ]

        st.markdown(f"**Inconsistências Identificadas:** {len(df_anomalias)} registros correspondentes aos filtros selecionados.")

        colunas_central = [
            'ID_FORNECEDOR', 'CNPJ_LIMPO', 'RAZAO_SOCIAL_INFORMADA',
            'SITUACAO_FORNECEDOR', 'DESCRICAO_SITUACAO', 'RISCO_CADASTRAL', 'VALOR_CONTRATO'
        ]
        col_existentes = [c for c in colunas_central if c in df_anomalias.columns]
        st.dataframe(df_anomalias[col_existentes], width='stretch')

        # Botão de Exportação
        if not df_anomalias.empty:
            csv_data = df_anomalias[col_existentes].to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Exportar Base de Inconsistências (.csv)",
                data=csv_data,
                file_name="lista_fornecedores_bloqueio_erp.csv",
                mime="text/csv"
            )
