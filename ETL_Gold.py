# -*- coding: utf-8 -*-
"""
ETL Gold: Modelagem Dimensional Star Schema, Tabela Bridge de CNAEs e Fato Completa
Preservando todas as colunas operacionais da Silver e garantindo que o app.py acesse todos os campos necessarios.
"""
import os
import pandas as pd
import numpy as np

SILVER_DIR = '/content/drive/MyDrive/Curriculo/Processos_Seletivos/Case_ABR_GUSTAVO_VAZ_2026/medallion/silver'
GOLD_DIR = '/content/drive/MyDrive/Curriculo/Processos_Seletivos/Case_ABR_GUSTAVO_VAZ_2026/medallion/gold'
os.makedirs(GOLD_DIR, exist_ok=True)

def executar_gold():
    origem = os.path.join(SILVER_DIR, 'fornecedores_enriquecidos.csv')
    if not os.path.exists(origem):
        origem = os.path.join(SILVER_DIR, 'fornecedores_higienizados.csv')
        if not os.path.exists(origem):
            print("Erro: Arquivo original nao encontrado na camada Silver.")
            return

    print(f"[GOLD] Carregando dados da camada Silver para modelagem: {origem}")
    df = pd.read_csv(origem, dtype={'CNPJ_LIMPO': str, 'CNAE_PRINCIPAL_CODIGO': str})
    df['CNPJ_LIMPO'] = df['CNPJ_LIMPO'].astype(str).str.zfill(14)

    # Garantindo que colunas criticas de enriquecimento existam (com valores padroes se nao existirem)
    colunas_enriquecimento = {
        'CNAES_SECUNDARIOS': np.nan,
        'CNAE_PRINCIPAL_CODIGO': np.nan,
        'CNAE_PRINCIPAL_DESCRICAO': np.nan,
        'SITUACAO_CADASTRAL': np.nan,
        'DESCRICAO_SITUACAO': np.nan,
        'UF_RFB': np.nan,
        'MUNICIPIO_RFB': np.nan,
        'VALOR_CONTRATO': 0.0,
        'CATEGORIA': 'Nao Especificado',
        'SITUACAO_FORNECEDOR': 'Ativo'
    }
    for col, v_padrao in colunas_enriquecimento.items():
        if col not in df.columns:
            df[col] = v_padrao

    # 1. Tabela Bridge para CNAEs secundários (N:M)
    print("[GOLD] Estruturando Tabela Bridge de CNAEs Secundarios (N:M)...")
    df_cnae_sec = df[['ID_FORNECEDOR', 'CNPJ_LIMPO', 'CNAES_SECUNDARIOS']].dropna(subset=['CNAES_SECUNDARIOS'])
    bridge_rows = []
    for _, row in df_cnae_sec.iterrows():
        cnaes = str(row['CNAES_SECUNDARIOS']).split(',')
        for cnae in cnaes:
            cnae_limpo = cnae.strip()
            if cnae_limpo and cnae_limpo != 'nan':
                bridge_rows.append({
                    'ID_FORNECEDOR': row['ID_FORNECEDOR'],
                    'CNPJ_LIMPO': row['CNPJ_LIMPO'],
                    'CNAE_CODIGO': cnae_limpo
                })
    if bridge_rows:
        df_bridge = pd.DataFrame(bridge_rows)
    else:
        df_bridge = pd.DataFrame(columns=['ID_FORNECEDOR', 'CNPJ_LIMPO', 'CNAE_CODIGO'])

    # 2. Dimensão CNAE
    print("[GOLD] Gerando Dimensao CNAE...")
    cnaes_principais = df[['CNAE_PRINCIPAL_CODIGO', 'CNAE_PRINCIPAL_DESCRICAO']].dropna().rename(columns={
        'CNAE_PRINCIPAL_CODIGO': 'CNAE_CODIGO',
        'CNAE_PRINCIPAL_DESCRICAO': 'CNAE_DESCRICAO'
    })
    if not df_bridge.empty:
        cnaes_secundarios = pd.DataFrame({'CNAE_CODIGO': df_bridge['CNAE_CODIGO'].unique()})
        cnaes_secundarios['CNAE_DESCRICAO'] = 'CNAE Secundario Cadastrado RFB'
        dim_cnae = pd.concat([cnaes_principais, cnaes_secundarios]).drop_duplicates(subset=['CNAE_CODIGO'], keep='first')
    else:
        dim_cnae = cnaes_principais.drop_duplicates(subset=['CNAE_CODIGO'], keep='first')

    # 3. Dimensão Geografia
    print("[GOLD] Gerando Dimensao Geografia...")
    dim_geo = df[['UF_RFB', 'MUNICIPIO_RFB']].dropna().drop_duplicates().reset_index(drop=True)
    dim_geo['ID_GEOGRAFIA'] = dim_geo.index + 1

    # 4. Dimensão Fornecedor (Completa e integrada)
    print("[GOLD] Gerando Dimensao Fornecedores...")
    cols_dim = [
        'ID_FORNECEDOR', 'CNPJ_LIMPO', 'CNPJ_RAIZ', 'MATRIZ_FILIAL',
        'RAZAO_SOCIAL_INFORMADA', 'SITUACAO_CADASTRAL', 'DESCRICAO_SITUACAO',
        'CNAE_PRINCIPAL_CODIGO', 'CNAE_PRINCIPAL_DESCRICAO', 'UF_RFB', 'MUNICIPIO_RFB'
    ]
    cols_presentes = [c for c in cols_dim if c in df.columns]
    dim_fornecedores = df[cols_presentes].drop_duplicates().copy()
    
    if 'UF_RFB' in dim_fornecedores.columns and 'MUNICIPIO_RFB' in dim_fornecedores.columns and not dim_geo.empty:
        dim_fornecedores = pd.merge(dim_fornecedores, dim_geo, on=['UF_RFB', 'MUNICIPIO_RFB'], how='left')
        # Mantemos UF_RFB e MUNICIPIO_RFB aqui para o Dashboard do app.py cruzar diretamente de forma robusta

    # 5. Tabela Fato Completa (Mantendo todas as colunas de auditoria e os metadados de negocio)
    print("[GOLD] Gerando Tabela Fato de Auditoria Completa...")
    fato_fornecedores = df.copy()

    # Classificação de Risco Operacional
    fato_fornecedores['RISCO_CADASTRAL'] = 'Regular'
    # if 'CNPJ_VALIDO' in fato_fornecedores.columns:
    #     fato_fornecedores.loc[fato_fornecedores['CNPJ_VALIDO'] == False, 'RISCO_CADASTRAL'] = 'Critico (CNPJ Invalido)'

    if 'DESCRICAO_SITUACAO' in df.columns:
        fato_fornecedores['DESCRICAO_SITUACAO_RFB'] = df['DESCRICAO_SITUACAO']
        fato_fornecedores.loc[
            (fato_fornecedores['DESCRICAO_SITUACAO_RFB'].isin(['BAIXADA', 'INAPTA', 'SUSPENSA', 'NULA'])),
            'RISCO_CADASTRAL'
        ] = 'Critico'
        # fato_fornecedores.drop(columns=['DESCRICAO_SITUACAO_RFB'], inplace=True, errors='ignore')

    # Salvando os arquivos modelados na camada Gold
    dim_fornecedores.to_csv(os.path.join(GOLD_DIR, 'dim_fornecedores.csv'), index=False, encoding='utf-8')
    dim_cnae.to_csv(os.path.join(GOLD_DIR, 'dim_cnae.csv'), index=False, encoding='utf-8')
    dim_geo.to_csv(os.path.join(GOLD_DIR, 'dim_geografia.csv'), index=False, encoding='utf-8')
    df_bridge.to_csv(os.path.join(GOLD_DIR, 'bridge_fornecedores_cnae.csv'), index=False, encoding='utf-8')
    fato_fornecedores.to_csv(os.path.join(GOLD_DIR, 'fato_fornecedores_auditoria.csv'), index=False, encoding='utf-8')
    
    print("[GOLD] Sucesso: Tabelas dimensionais e Fato consolidada exportadas!")

if __name__ == '__main__':
    executar_gold()
