# -*- coding: utf-8 -*-
"""
ETL Enriquecimento: Integração de APIs de terceiros para saneamento cadastral
"""
import os
import time
import requests
import pandas as pd
import sys

SILVER_DIR = 'medallion/silver'

def consultar_cnpj_api(cnpj):
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    try:
        response = requests.get(url, timeout=10)
        print(response.status_code)
        if response.status_code in (500, 503):
            print("Erro 503: Serviço indisponível na BrasilAPI. Tentando Novamente...")
            # sys.exit(1)  # Encerra o script completamente
            time.sleep(5)
            return consultar_cnpj_api(cnpj)
        elif response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            time.sleep(3)
            return consultar_cnpj_api(cnpj)
    except Exception:
        pass
    return None

def executar_enriquecimento():
    origem = os.path.join(SILVER_DIR, 'fornecedores_higienizados.csv')
    destino = os.path.join(SILVER_DIR, 'fornecedores_enriquecidos.csv')

    if not os.path.exists(origem):
        print("Erro: Base Silver de fornecedores não localizada.")
        return

    df = pd.read_csv(origem, dtype={'CNPJ_LIMPO': str})
    cnpjs_validos = df[df['CNPJ_VALIDO'] == True]['CNPJ_LIMPO'].unique()

    print(f"[ENRIQUECIMENTO] Iniciando consulta de enriquecimento para os 10 primeiros CNPJs válidos...")
    amostra = cnpjs_validos[:len(cnpjs_validos)]
    registros = []

    for i, cnpj in enumerate(amostra, 1):
        print(f"({i}/{len(amostra)}) Buscando dados cadastrais para o CNPJ: {cnpj}")
        dados = consultar_cnpj_api(cnpj)
        if dados:
            registros.append({
                'CNPJ_LIMPO': str(cnpj).zfill(14),
                'SITUACAO_CADASTRAL': dados.get('situacao_cadastral'),
                'DATA_SITUACAO_CADASTRAL': dados.get('data_situacao_cadastral'),
                'DESCRICAO_SITUACAO': dados.get('descricao_situacao_cadastral', 'ATIVA'),
                'CNAE_PRINCIPAL_CODIGO': dados.get('cnae_fiscal'),
                'CNAE_PRINCIPAL_DESCRICAO': dados.get('cnae_fiscal_descricao'),
                'CNAES_SECUNDARIOS': ",".join([str(c.get('codigo')) for c in dados.get('cnaes_secundarios', []) if c.get('codigo')]),
                'DESCRICAO_CNAES_SECUNDARIOS': ",".join([str(c.get('descricao')) for c in dados.get('cnaes_secundarios', []) if c.get('descricao')]),
                'UF_RFB': dados.get('uf'),
                'MUNICIPIO_RFB': dados.get('municipio')
            })
            time.sleep(0.5)

    df_rfb = pd.DataFrame(registros)
    print(f"[ENRIQUECIMENTO] Linhas Não nulas RFB: {len(df_rfb)}")
    if not df_rfb.empty:
        df_rfb['CNPJ_LIMPO'] = df_rfb['CNPJ_LIMPO'].astype(str).str.zfill(14)
        df_final = pd.merge(df, df_rfb, on='CNPJ_LIMPO', how='left')
    else:
        df_final = df.copy()

    df_final.to_csv(destino, index=False, encoding='utf-8')
    print(f"[ENRIQUECIMENTO] Arquivo integrado gravado com sucesso em: {destino}")

if __name__ == '__main__':
    executar_enriquecimento()
