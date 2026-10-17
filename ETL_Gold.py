# -*- coding: utf-8 -*-
"""
ETL Gold: Modelagem Dimensional Star Schema, Tabela Bridge de CNAEs e Fato Completa
Preservando todas as colunas operacionais da Silver e garantindo que o app.py acesse todos os campos necessarios.
"""
import os
import pandas as pd
import numpy as np
import unicodedata

SILVER_DIR = 'medallion/silver'
GOLD_DIR = 'medallion/gold'
os.makedirs(GOLD_DIR, exist_ok=True)

def executar_gold():
    origem = os.path.join(SILVER_DIR, 'fornecedores_enriquecidos.csv')
    if not os.path.exists(origem):
        print("Erro: Arquivo original nao encontrado na camada Silver.")
        return

    print(f"[GOLD] Carregando dados da camada Silver para modelagem: {origem}")
    df = pd.read_csv(origem, dtype={'CNPJ_LIMPO': str, 'CNAE_PRINCIPAL_CODIGO': str})
    df['DESCRICAO_SITUACAO'] = df['DESCRICAO_SITUACAO'].fillna('CNPJ INVALIDO')
    df['SITUACAO_CADASTRAL'] = df['SITUACAO_CADASTRAL'].fillna('0.0')
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

    # 1. Tabela Bridge para CNAEs (N:M)
    print("[GOLD] Estruturando Tabela Bridge de CNAEs Secundarios (N:M)...")
    
    # 1. Função de De-Para baseada em regras de palavras-chave para classificar o CNAE nas categorias oficiais
    def classificar_cnae_para_categoria(desc_cnae):
        if pd.isna(desc_cnae):
            return 'Não Classificado'
        
        d = str(desc_cnae).lower()
        
        # Regras de correspondência por palavras-chave
        if any(k in d for k in ['tecnologia', 'software', 'informática', 'computador', 'dados', 'internet', 'portal', 'desenvolvimento de programas']):
            return 'Serviços de Tecnologia e Software'
        
        elif any(k in d for k in ['transporte', 'carga', 'logística', 'frete', 'veículo', 'automóvel', 'malote', 'táxi', 'fretamento', 'armazenagem', 'mudanças']):
            return 'Logística, Transporte e Frota'
        
        elif any(k in d for k in ['consultoria', 'auditoria', 'gestão empresarial', 'administração', 'planejamento', 'organização']):
            return 'Consultoria e Auditoria Empresarial'
        
        elif any(k in d for k in ['segurança', 'vigilância', 'portaria', 'investigação']):
            return 'Segurança Patrimonial e Portaria'
        
        elif any(k in d for k in ['escritório', 'papelaria', 'equipamentos', 'suprimentos', 'material', 'comércio varejista', 'cosméticos', 'vestuário', 'bebidas']):
            return 'Suprimentos e Equipamentos de Escritório'
        
        elif any(k in d for k in ['engenharia', 'construção', 'manutenção', 'reforma', 'instalação', 'elétrico', 'hidráulicos', 'pintura', 'limpeza', 'cabeleireiros', 'lavagem']):
            return 'Engenharia e Manutenção Predial'
        
        elif any(k in d for k in ['jurídico', 'advocacia', 'direito', 'contabilidade', 'contábeis']):
            return 'Serviços Jurídicos e Contábeis'
        
        elif any(k in d for k in ['marketing', 'publicidade', 'propaganda', 'mídia', 'eventos', 'feiras', 'congressos', 'fotografia', 'design']):
            return 'Marketing, Mídia e Eventos'
            
        else:
            return 'Outros / Geral'

    # 2. Mapeamento auxiliar de códigos CNAE para descrições padrão (garantia de integridade)
    cnae_map = {}
    if 'CNAE_PRINCIPAL_CODIGO' in df.columns and 'CNAE_PRINCIPAL_DESCRICAO' in df.columns:
        for _, row in df.iterrows():
            if pd.notna(row['CNAE_PRINCIPAL_CODIGO']) and pd.notna(row['CNAE_PRINCIPAL_DESCRICAO']):
                try:
                    cod_str = str(int(float(row['CNAE_PRINCIPAL_CODIGO']))).zfill(7)
                    cnae_map[cod_str] = str(row['CNAE_PRINCIPAL_DESCRICAO']).strip()
                except ValueError:
                    pass

    processed_rows = []

    for _, row in df.iterrows():
        base_info = {
            'ID_FORNECEDOR': row['ID_FORNECEDOR'],
            'CNPJ': row['CNPJ'],
            'CATEGORIA_FORNECIMENTO': row['CATEGORIA_FORNECIMENTO']
        }
        
        # Linha do CNAE Principal
        cnae_princ_cod = row['CNAE_PRINCIPAL_CODIGO']
        cnae_princ_desc = row['CNAE_PRINCIPAL_DESCRICAO']
        
        if pd.notna(cnae_princ_cod):
            try:
                cnae_princ_cod_str = str(int(float(cnae_princ_cod)))
            except ValueError:
                cnae_princ_cod_str = str(cnae_princ_cod)
                
            r_princ = base_info.copy()
            r_princ['CNAE_CODIGO'] = cnae_princ_cod_str
            r_princ['CNAE_DESCRICAO'] = cnae_princ_desc
            r_princ['TIPO_CNAE'] = 'Principal'
            
            # Atribui a categoria mapeada pelo De-Para
            r_princ['CATEGORIA_REAL_MAPEADA'] = classificar_cnae_para_categoria(cnae_princ_desc)
            
            processed_rows.append(r_princ)
            
        # Linhas dos CNAEs Secundários
        cnaes_sec = row['CNAES_SECUNDARIOS']
        descs_sec = row['DESCRICAO_CNAES_SECUNDARIOS']
        
        if pd.notna(cnaes_sec) and str(cnaes_sec).strip() != '':
            cod_list = [c.strip() for c in str(cnaes_sec).split(',')]
            desc_list = [d.strip() for d in str(descs_sec).split(',')] if pd.notna(descs_sec) else []
            
            if len(cod_list) == len(desc_list):
                for c, d in zip(cod_list, desc_list):
                    r_sec = base_info.copy()
                    r_sec['CNAE_CODIGO'] = c
                    r_sec['CNAE_DESCRICAO'] = d
                    r_sec['TIPO_CNAE'] = 'Secundário'
                    r_sec['CATEGORIA_REAL_MAPEADA'] = classificar_cnae_para_categoria(d)
                    processed_rows.append(r_sec)
            else:
                for idx_c, c in enumerate(cod_list):
                    c_norm = c.zfill(7)
                    desc = cnae_map.get(c_norm, None)
                    if not desc and idx_c < len(desc_list):
                        desc = desc_list[idx_c]
                    
                    r_sec = base_info.copy()
                    r_sec['CNAE_CODIGO'] = c
                    r_sec['CNAE_DESCRICAO'] = desc
                    r_sec['TIPO_CNAE'] = 'Secundário'
                    r_sec['CATEGORIA_REAL_MAPEADA'] = classificar_cnae_para_categoria(desc)
                    processed_rows.append(r_sec)

    # 3. Criação do DataFrame final df_bridge
    df_bridge = pd.DataFrame(processed_rows)

    # 4. Comparação final entre a Categoria Inicial e a Categoria Mapeada (tolerante a maiúsculas/minúsculas)
    df_bridge['CATEGORIA_COMPATIVEL'] = (
        df_bridge['CATEGORIA_FORNECIMENTO'].astype(str).str.strip().str.lower() == 
        df_bridge['CATEGORIA_REAL_MAPEADA'].astype(str).str.strip().str.lower()
    )

    ## comparar se ao menos um CNAE de cada fornecedor é compativel
    # 1. Agrupa o df_bridge por ID_FORNECEDOR verificando se há pelo menos um True na validação
    df_validacao = (
        df_bridge.groupby('ID_FORNECEDOR')['CATEGORIA_COMPATIVEL']
        .any()
        .reset_index()
        .rename(columns={'CATEGORIA_COMPATIVEL': 'TEM_CATEGORIA_COMPATIVEL'})
    )

    # 2. Dimensão CNAE
    print("[GOLD] Gerando Dimensao CNAE...")
    dim_cnae = df_bridge[['CNAE_CODIGO', 'CNAE_DESCRICAO']].dropna()
    dim_cnae = dim_cnae.drop_duplicates(subset=['CNAE_CODIGO'], keep='first')

    # 3. Dimensão Geografia
    print("[GOLD] Gerando Dimensao Geografia...")
    dim_geo = df[['UF_RFB', 'MUNICIPIO_RFB']].dropna().drop_duplicates().reset_index(drop=True)
    dim_geo['ID_GEOGRAFIA'] = dim_geo.index + 1

    # Dicionário de mapeamento de siglas para nomes dos estados
    uf_para_estado = {
        'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas', 'BA': 'Bahia',
        'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo', 'GO': 'Goiás',
        'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul', 'MG': 'Minas Gerais',
        'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná', 'PE': 'Pernambuco', 'PI': 'Piauí',
        'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte', 'RS': 'Rio Grande do Sul',
        'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina', 'SP': 'São Paulo',
        'SE': 'Sergipe', 'TO': 'Tocantins'
    }

    def remover_acentos(texto):
        if not isinstance(texto, str):
            return texto
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join([c for c in nfkd if not unicodedata.combining(c)]).title()

    # 1. Mapeia a sigla para o nome completo
    # 2. Aplica a remoção de acentos e formatação title case
    dim_geo['estado'] = dim_geo['UF_RFB'].str.upper().map(uf_para_estado).apply(remover_acentos)


    # 5. Tabela Fato Completa (Mantendo todas as colunas de auditoria e os metadados de negocio)
    print("[GOLD] Gerando Tabela Fato...")
    fato_fornecedores = df.copy()

    fato_fornecedores['DESCRICAO_SITUACAO'] = fato_fornecedores['DESCRICAO_SITUACAO'].fillna('CNPJ INVALIDO')

    # 2. Faz o merge com o dataframe existente fato_fornecedores
    fato_fornecedores = fato_fornecedores.merge(
        df_validacao, 
        on='ID_FORNECEDOR', 
        how='left'
    )
    
    # 3. Trata eventuais valores nulos (caso algum fornecedor não conste na bridge) preenchendo com False
    fato_fornecedores['TEM_CATEGORIA_COMPATIVEL'] = fato_fornecedores['TEM_CATEGORIA_COMPATIVEL'].fillna(False)

    
    # Classificação de Risco Operacional
    fato_fornecedores['RISCO_CADASTRAL'] = 'Regular'

    # 3. Novo Critério: Se a categoria não for compatível e o risco ainda for Regular, muda para 'Alerta'
    if 'TEM_CATEGORIA_COMPATIVEL' in fato_fornecedores.columns:
        fato_fornecedores.loc[
            (fato_fornecedores['TEM_CATEGORIA_COMPATIVEL'] == False) & 
            (fato_fornecedores['RISCO_CADASTRAL'] == 'Regular'),
            'RISCO_CADASTRAL'
        ] = 'Alerta'

    # 1. Critério de CNPJ Inválido
    if 'CNPJ_VALIDO' in fato_fornecedores.columns:
        fato_fornecedores.loc[fato_fornecedores['CNPJ_VALIDO'] == False, 'RISCO_CADASTRAL'] = 'Critico'

    # 2. Critério de Situação Cadastral RFB (Baixada, Inapta, etc.)
    if 'DESCRICAO_SITUACAO' in df.columns:
        fato_fornecedores['DESCRICAO_SITUACAO_RFB'] = df['DESCRICAO_SITUACAO']
        fato_fornecedores.loc[
            (fato_fornecedores['DESCRICAO_SITUACAO_RFB'].isin(['BAIXADA', 'INAPTA', 'SUSPENSA', 'NULA'])),
            'RISCO_CADASTRAL'
        ] = 'Critico'
        fato_fornecedores.drop(columns=['DESCRICAO_SITUACAO_RFB'], inplace=True, errors='ignore')
    
    # 4. Dimensão Fornecedor (Completa e integrada)
    print("[GOLD] Gerando Dimensao situacao cadastral...")
    cols_dim = [
        'SITUACAO_CADASTRAL','DESCRICAO_SITUACAO'
    ]
    cols_presentes = [c for c in cols_dim if c in fato_fornecedores.columns]
    dim_situacao = df[cols_presentes].drop_duplicates().copy()

    # 5, Dimensão Categoria de serviço
    print("[GOLD] Gerando Dimensao categoria...")
    cols_dim_cat = [
            'CATEGORIA_FORNECIMENTO'
        ]
    cols_presentes = [c for c in cols_dim_cat if c in df.columns]
    dim_cat = df[cols_presentes].drop_duplicates().copy()


    #6. Dimensão fornecedor
    print("[GOLD] Gerando Dimensao fornecedor...")
    cols_dim_fornecedor = [
            'ID_FORNECEDOR','RAZAO_SOCIAL_INFORMADA','STATUS_HOMOLOGACAO','DATA_ULTIMO_PAGAMENTO',
            'CNPJ_LIMPO', 'CNPJ_RAIZ','MATRIZ_FILIAL','CNAE_PRINCIPAL_CODIGO'
        ]
    cols_presentes = [c for c in cols_dim_fornecedor if c in df.columns]
    dim_fornecedores = df[cols_presentes].drop_duplicates().copy()


    fato_fornecedores = fato_fornecedores[['ID_FORNECEDOR','SITUACAO_CADASTRAL' ,'CNAE_PRINCIPAL_CODIGO',
                                           'CATEGORIA_FORNECIMENTO','MUNICIPIO_RFB','VALOR_CONTRATADO_ANUAL','RISCO_CADASTRAL',
                                           'CNPJ_VALIDO','SITUACAO_FORNECEDOR', 'TEM_CATEGORIA_COMPATIVEL']]

        
    # Salvando os arquivos modelados na camada Gold
    dim_situacao.to_csv(os.path.join(GOLD_DIR, 'dim_situacao_cadastral.csv'), index=False, encoding='utf-8')
    dim_fornecedores.to_csv(os.path.join(GOLD_DIR, 'dim_fornecedores.csv'), index=False, encoding='utf-8')
    dim_cat.to_csv(os.path.join(GOLD_DIR, 'dim_categoria_fornecimento.csv'), index=False, encoding='utf-8')
    dim_cnae.to_csv(os.path.join(GOLD_DIR, 'dim_cnae.csv'), index=False, encoding='utf-8')
    dim_geo.to_csv(os.path.join(GOLD_DIR, 'dim_geografia.csv'), index=False, encoding='utf-8')
    df_bridge.to_csv(os.path.join(GOLD_DIR, 'bridge_fornecedores_cnae.csv'), index=False, encoding='utf-8')
    fato_fornecedores.to_csv(os.path.join(GOLD_DIR, 'fato_fornecedores_auditoria.csv'), index=False, encoding='utf-8')
    
    print("[GOLD] Sucesso: Tabelas dimensionais e Fato consolidada exportadas!")

if __name__ == '__main__':
    executar_gold()