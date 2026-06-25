# ☀️ Aveiro CER Solar — Potencial Fotovoltaico e Comunidades de Energia Renovável

**Projeto académico | Mestrado UA | Seminário 2025/2026 — Grupo 4**

Análise geoespacial e económica do potencial de instalação solar fotovoltaica no município de Aveiro, ao nível do código postal de 7 dígitos (CP7) e dos Postos de Transformação de Distribuição (PTD) da E-Redes.

---

## 📋 Resumo do Projeto

O projeto estima a viabilidade técnica e económica de Comunidades de Energia Renovável (CER) em Aveiro, cobrindo quatro etapas principais:

| Notebook | Tema | Output principal |
|----------|------|-----------------|
| `04` | Produção PV + Consumo por CP7 | `comparacao_final_limpa_cp7.csv` |
| `01` | Roteamento espacial (edifícios → PTD) + Dimensionamento físico | `dashboard_ptd_capacidade_real.gpkg` |
| `02` | Análise económica por PTD (VAL, TIR, Payback) | `analise_economica_ptd.csv` |
| `03` | Econometria espacial (Moran, SAR, SEM) + Optimização MILP | `milp_resultados_cp7_88k.csv` |

**Resultados chave:**
- Produção solar potencial estimada: **292 GWh/ano**
- Consumo total validado (zona de cruzamento): **427 GWh/ano**
- Taxa de autossuficiência global: **52.8%**
- Com orçamento de 5 M€ (MILP): **359 de 558 CP7s autossuficientes (64.3%)**

---

## 🗂️ Estrutura do Repositório

```
aveiro-cer-solar/
│
├── notebooks/
│   ├── 01_roteamento_espacial_ptd.ipynb      # Voronoi de rede, spatial join, empacotamento
│   ├── 02_analise_economica_ptd.ipynb         # VAL, TIR, Payback por PTD
│   ├── 03_econometria_espacial_milp.ipynb     # Moran, SAR/SEM, MILP
│   └── 04_producao_pv_consumo_cp7.ipynb       # PVGIS, edifícios GPKG, consumo E-Redes
│
├── data/
│   ├── raw/                   # Dados de entrada (ver secção de dados)
│   └── processed/             # Ficheiros gerados pelos notebooks
│
├── outputs/                   # Mapas e ficheiros finais exportados
│
├── docs/
│   └── metodologia.md         # Notas metodológicas detalhadas
│
├── environment.yml            # Ambiente Conda reproduzível
├── requirements.txt           # Dependências pip
└── README.md
```

---

## 📦 Dados de Entrada (não incluídos no repositório)

Os seguintes ficheiros de dados **não estão incluídos** por limitações de tamanho e privacidade. Devem ser colocados em `data/raw/`:

| Ficheiro | Descrição | Fonte |
|----------|-----------|-------|
| `edificios_aveiro.gpkg` | Pegadas dos edifícios com CP7 atribuído | Cartografia OpenStreetMap / Câmara de Aveiro |
| `pvgis_aveiro.csv` | Irradiação solar horária (série multi-anual) | [PVGIS — JRC](https://re.jrc.ec.europa.eu/pvg_tools/) |
| `serie_consumo_cp7_2024_2025_v2.csv` | Leituras horárias de energia ativa por CP7 | E-Redes |
| `VoronoiPTD_Areas_Servico_Rede.gpkg` | Áreas de serviço dos PTDs (Voronoi de rede) | E-Redes / OSMnx |
| `producao_pv_cp7.gpkg` | Output do NB04 — polígonos CP7 com produção PV | Gerado pelo notebook 04 |

> **Nota:** Devido a limitação de tamanho, os ficheiros `edificios_aveiro.gpkg` e `serie_consumo_cp7_2024_2025_v2.csv` foram adicionados ao github através do release, estando disponíveis nesta secção através do link: https://github.com/gabrielaneves21404-rgb/Seminario/releases/tag/Dados_semin%C3%A1rio
> 

---

## 🚀 Reprodução Rápida

### 1. Clonar o repositório

```bash
git clone https://github.com/<utilizador>/aveiro-cer-solar.git
cd aveiro-cer-solar
```

### 2. Criar o ambiente

**Com Conda (recomendado):**
```bash
conda env create -f environment.yml
conda activate aveiro-cer
```

**Com pip:**
```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 3. Colocar os dados

Copiar os ficheiros de entrada para `data/raw/` (ver tabela acima).

### 4. Correr os notebooks por ordem

```bash
jupyter lab
```

Executar pela ordem numérica: **04 → 01 → 02 → 03**

> O notebook 04 gera os ficheiros base que os restantes consomem.

---

## 🔧 Parâmetros Configuráveis

Os parâmetros principais estão no topo de cada notebook:

| Parâmetro | Valor padrão | Notebook |
|-----------|-------------|----------|
| `ETA_PAINEL` | 0.20 (20%) | NB04 |
| `PR` | 0.80 | NB04 |
| `FATOR_OCUPACAO_RESIDENCIAL` | 0.40 | NB04 |
| `FATOR_EMPACOTAMENTO` | 0.85 | NB01 |
| `AREA_PAINEL_M2` | 2.0 m² | NB01 |
| `POTENCIA_PAINEL_KWP` | 0.450 kWp | NB01/02 |
| `CUSTO_POR_PAINEL_EUR` | 1200 €/painel | NB02 |
| `TAXA_DESCONTO` | 7% | NB02 |
| `HORIZONTE_ANOS` | 25 anos | NB02 |
| `ORCAMENTO` | 5 000 000 € | NB03 |

---

## 🧠 Metodologia Resumida

### Notebook 04 — Produção PV e Consumo
- **PVGIS:** Parse da série horária de irradiação global no plano inclinado H(i). Média: **1860 kWh/m²/ano**
- **Edifícios:** Área útil = `area_fragmento × 0.40`. Produção = `H(i) × area_util × η × PR`
- **Consumo:** Extrapolação anual robusta por CP7 (mín. 70 registos horários)
- **Cruzamento:** Inner merge → 558 CP7s comuns. Taxa global: **52.8%**

### Notebook 01 — Roteamento Espacial
- **Spatial Join por centroide** (indivisibilidade da infraestrutura 1:1)
- **Cobertura híbrida:** `within` + `sjoin_nearest` (fallback ≤ 1000 m)
- **Problema de empacotamento:** `floor((area × 0.85) / 2.0 m²)`

### Notebook 02 — Análise Económica
- Distinção **autoconsumo** (0.25 €/kWh) vs **excedente RESP** (0.05 €/kWh)
- Fluxos de caixa com degradação de 0.5%/ano durante 25 anos
- Indicadores: VAL, TIR (bissecção numérica), Payback simples

### Notebook 03 — Econometria Espacial + MILP
- **Moran Global:** I = 0.1703, p < 0.001 → autocorrelação espacial positiva significativa
- **LISA:** 105 CP7s significativos (32 HH, 49 LL, 18 LH, 6 HL)
- **SAR vs SEM:** AIC SAR (6494.9) < SEM (6502.0) → SAR preferível
- **MILP (PuLP/CBC):** 112 CP7s financiados, 4.89 M€ utilizados, cobertura 64.3%

---

## 📊 Outputs Gerados

| Ficheiro | Descrição |
|----------|-----------|
| `producao_pv_cp7.csv` | Produção PV estimada por CP7 |
| `comparacao_final_limpa_cp7.csv` | Produção vs. consumo por CP7 |
| `potencial_com_mapeamento_ptd.csv` | Edifícios mapeados para PTDs |
| `dimensionamento_realista_paineis_ptd.csv` | Painéis instaláveis por PTD |
| `dashboard_ptd_capacidade_real.gpkg` | GeoPackage final para QGIS/Streamlit |
| `analise_economica_ptd.csv` | VAL, TIR, Payback por PTD |
| `resultados_sar_cp7_88k.gpkg` | Resíduos e fitted values do SAR |
| `milp_resultados_cp7_88k.csv` | Selecção MILP de CP7s a financiar |
| `mapa_lisa_autossuficiencia_88k.png` | Mapa LISA dos clusters espaciais |
| `mapa_milp_aveiro_88k.png` | Mapa da solução MILP |

---

## 👥 Grupo 4 — SEM 2025/2026

Projeto desenvolvido no âmbito do Mestrado da Universidade de Aveiro.

---

## 📄 Licença

Este repositório é disponibilizado para fins académicos. Os dados da E-Redes não podem ser redistribuídos.
