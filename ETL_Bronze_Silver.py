# -*- coding: utf-8 -*-
"""
ETL Bronze & Silver: Higienização e Validação do Módulo 11 da RFB
"""
import os
import re
import pandas as pd

BRONZE_DIR = 'medallion/bronze'
SILVER_DIR = 'medallion/silver'

os.makedirs(BRONZE_DIR, exist_ok=True)
os.makedirs(SILVER_DIR, exist_ok=True)

def validar_cnpj(cnpj_str):
    cnpj = re.sub(r'\D', '', str(cnpj_str)).zfill(14)
    if len(cnpj) != 14 or cnpj in [str(i) * 14 for i in range(10)]:
        return False
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_1 = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    resto_1 = soma_1 % 11
    digito_1 = 0 if resto_1 < 2 else 11 - resto_1
    if int(cnpj[12]) != digito_1:
        return False
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma_2 = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    resto_2 = soma_2 % 11
    digito_2 = 0 if resto_2 < 2 else 11 - resto_2
    return int(cnpj[13]) == digito_2

def executar_bronze_silver(origem_xlsx):
    # Bronze
    destino_bronze = os.path.join(BRONZE_DIR, 'fornecedores_bruto.csv')
    df_raw = pd.read_excel(origem_xlsx)
    df_raw.to_csv(destino_bronze, index=False, encoding='utf-8')
    print(f"[BRONZE] Dados salvos com sucesso em: {destino_bronze}")

    # Silver
    destino_silver = os.path.join(SILVER_DIR, 'fornecedores_higienizados.csv')
    df = df_raw.copy()
    df['CNPJ_LIMPO'] = df['CNPJ'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(14)
    df['CNPJ_VALIDO'] = df['CNPJ_LIMPO'].apply(validar_cnpj)
    df['CNPJ_RAIZ'] = df['CNPJ_LIMPO'].str[:8]
    df['MATRIZ_FILIAL'] = df['CNPJ_LIMPO'].str[8:12].apply(lambda x: 'Matriz' if x == '0001' else 'Filial')

    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str).str.strip()

    df.to_csv(destino_silver, index=False, encoding='utf-8')
    print(f"[SILVER] Dados limpos e validados salvos em: {destino_silver}")

if __name__ == '__main__':
    executar_bronze_silver('base_fornecedores_homologados.xlsx')
