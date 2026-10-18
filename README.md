# 🛡️ Portal de Compliance & Risco Cadastral B2B - Pipeline Medallion

Este repositório contém a solução ponta a ponta desenvolvida para a higienização, enriquecimento, modelagem analítica e monitoramento de risco de fornecedores contratados. O pipeline foi estruturado sob as melhores práticas de Engenharia de Dados Modernas, aplicando a arquitetura **Medallion (Bronze -> Silver -> Gold)**, garantindo resiliência de API, modelagem dimensional e entrega de valor via dashboard interativo.

---

## 🛠️ Arquitetura da Solução e Justificativa Tecnológica

A escolha metodológica deste projeto reflete padrões industriais voltados à escalabilidade, robustez e capacidade de auditoria histórica.

```
  [ Origem: Excel ] ──> [ Camada Bronze: raw/ingestão ]
                               │
                               ▼
                    [ Camada Silver: higienização ] ──> [ API Externa: BrasilAPI / RFB ]
                               │
                               ▼
                    [ Camada Gold: dimensional (Star Schema) ] ──> [ Power BI / Streamlit ]
```

### 1. Por que a Arquitetura Medallion?
A divisão em camadas de dados permite o isolamento de responsabilidades e facilita a governança de dados:
* **Bronze (Ingestão)**: Preserva uma cópia fiel e imutável dos dados brutos recebidos, garantindo a rastreabilidade (*lineage*) caso o arquivo original precise ser reauditado.
* **Silver (Higienização e Enriquecimento)**: Aplica regras rígidas de qualidade técnica (como a validação matemática de CNPJs via **Algoritmo do Módulo 11**) e realiza a integração com APIs de terceiros para saneamento cadastral.
* **Gold (Modelagem Dimensional)**: Transforma os dados em esquemas altamente otimizados para consumo de Business Intelligence (**Star Schema**), desacoplando complexidades técnicas (como a cardinalidade N:M de CNAEs Secundários por meio de uma **Tabela Bridge**) de modo a otimizar a performance de consultas.

### 2. Integração de APIs e Tratamento Resiliente de Erros
Para o saneamento cadastral, escolheu-se a **BrasilAPI** como canal de consulta aos dados oficiais da Receita Federal do Brasil (RFB) por ser gratuita, não requerer credenciais complexas de infraestrutura corporativa para testes rápidos e possuir documentação sólida.

Entretanto, chamadas a APIs públicas exigem técnicas de tolerância a falhas. O pipeline de dados desenvolvido implementa:
* **Rate Limiting (Status 429)**: Mecanismo de *backoff* temporizado (`time.sleep`) para aguardar o reestabelecimento da taxa de requisições permitida.
* **Tratamento de Indisponibilidade do Serviço (Erros 500/503)**: A rotina foi desenvolvida para tratar instabilidades internas do servidor remoto. Se a API retornar um erro `500` (Internal Server Error) ou `503` (Service Unavailable), o pipeline captura a exceção de forma defensiva, salvando o estado consolidado até o momento (*checkpointing*) e encerrando graciosamente sem corromper a base de dados local ou interromper a execução do fluxo operacional de maneira catastrófica.


Para os dados de CNAE, foi realizada consulta no site de categorias de CNAE do IBGE.

---

## 🖥️ Aplicativo Visual Interativo (app.py)

O aplicativo visual foi desenvolvido em **Streamlit** e serve como a camada final de apresentação de dados (*Gold*) para tomada de decisão e inteligência de compliance.

### Estrutura de Abas do Aplicativo:
1. **Painel Executivo**: KPIs estratégicos, volumetria consolidada sob contratos ativos e índice global de conformidade.
2. **Auditoria de CNAEs**: Gráfico detalhado das principais atividades principais e secundárias utilizando a modelagem de relacionamento muitos-para-muitos da **Tabela Bridge**.
3. **Geografia e Grupos**: Mapeamento da concentração física por estados (UF) e agrupamento lógico de filiais por CNPJ Raiz.
4. **Central de Bloqueio**: Tela de busca reativa e exportação rápida de relatórios contendo inconsistências cadastrais graves para atuação operacional rápida de barramento no ERP.

---

## 🧭 Como Executar Localmente o app.py (COMO_EXECUTAR.txt)

Para garantir a portabilidade do projeto localmente sem as dependências diretas de conexão externa do Colab:

1. **Preparação de Ambiente**:
   ```bash
   pip install streamlit pandas plotly openpyxl xlsxwriter
   ```
2. **Execução de Contingência (Tratamento de Portas e CORS)**:
   Para rodar o app de forma otimizada ignorando limitações de CORS e forçando uma porta livre alternativa (ex: `8502`), use:
   ```bash
   streamlit run app.py --server.port 8502 --server.enableCORS false --server.enableXsrfProtection false
   ```
3. **Funcionamento 100% Offline**:
   O `app.py` lê os dados pré-gerados da pasta `medallion/gold`. Mantendo essa pasta junto com o script no seu computador, o dashboard funciona imediatamente sem a necessidade de novas consultas externas de API.

---

## 📂 Estrutura do Repositório

* **`ETL_Bronze_Silver.py`**: Rotina de ingestão e higienização utilizando validação do Módulo 11.
* **`ETL_Enriquecimento_API.py`**: Integração resiliente com a BrasilAPI.
* **`ETL_Gold.py`**: Modelagem dimensional e aplicação de regras de risco cadastral.
* **`app.py`**: Código fonte completo do portal interativo Streamlit.
* **`modelo_dados_powerbi.xlsx`**: Planilha consolidada de suporte para importação direta no Power BI Desktop.
* **`COMO_EXECUTAR.txt`**: Manual de contingência técnica de portas e execução local.