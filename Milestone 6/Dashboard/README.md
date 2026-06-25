# ☀️ Dashboard CER Aveiro — PTD

Dashboard interativo em Streamlit para análise de viabilidade técnica e económica da implementação de **Comunidades de Energia Renovável (CER)** em Aveiro, por Posto de Transformação e Distribuição (PTD).

> Projeto desenvolvido no âmbito da Universidade de Aveiro.  
> Autoras: Carolina Raposo · Gabriela Silva · Rebeca Freitas

---

## 📁 Estrutura da pasta

```
.
├── app.py
├── requirements.txt
├── VoronoiPTD_Areas_Servico_Rede.gpkg
├── analise_economica_ptd.csv
├── Edifícios_Câmara.csv
├── Ptd_zonas.csv
├── ua.png                          # opcional
└── painel.png                      # opcional
```

### Descrição dos ficheiros

| Ficheiro | Descrição |
|---|---|
| `app.py` | Aplicação Streamlit principal |
| `requirements.txt` | Dependências Python |
| `VoronoiPTD_Areas_Servico_Rede.gpkg` | Geometria dos PTDs (colunas: `fid`, `ptd_id`, `n_nos`, `area_km2`) |
| `analise_economica_ptd.csv` | Indicadores económicos por PTD (painéis, custo, VAL, TIR, payback) — separador `;` |
| `Edifícios_Câmara.csv` | Edifícios da Câmara Municipal (colunas: `nome`, `latitude`, `longitude`) |
| `Ptd_zonas.csv` | Zona/freguesia de cada PTD (colunas: `ptd_id`, `zona`) |
| `ua.png` | Logo da Universidade de Aveiro *(só estética na página de Apresentação)* |
| `painel.png` | Imagem de painel solar *(só estética na página de Apresentação)* |

> Os ficheiros `ua.png`, `painel.png` e `Ptd_zonas.csv` são **opcionais** — a app corre normalmente sem eles.

---

## 🚀 Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/<utilizador>/<repositorio>.git
cd <repositorio>
```

### 2. Criar e ativar ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

> **Nota para Windows — GeoPandas/Fiona:** se o `pip install` falhar a compilar o GDAL, usa Conda:
> ```bash
> conda install -c conda-forge geopandas fiona shapely
> pip install streamlit streamlit-folium folium plotly
> ```

---

## ▶️ Execução

```bash
streamlit run app5.py
```

---

## 🗂️ Estrutura do dashboard

| Página | Conteúdo |
|---|---|
| 🏠 **Apresentação** | Contexto do projeto, metodologia e indicadores globais do município (nº de PTDs, painéis, potência total, investimento, PTDs com edifícios da câmara) |
| 🗺️ **Mapa Geral — Todos os PTDs** | Mapa interativo de todos os PTDs coloridos por nº de painéis instaláveis, com popups de painéis/custo/payback/VAL/TIR, KPIs agregados, filtros e Top 10 |
| 🏛️ **Mapa — PTDs com Edifícios da Câmara** | Igual ao anterior, restrito aos PTDs cuja área de serviço (Voronoi) contém pelo menos um edifício da câmara, com pontos dos edifícios marcados |
| ⚡ **Produção vs Consumo** | Análise do rácio produção/consumo por PTD, mapa de autossuficiência energética e Top 10 PTDs com maior rácio |

---

## 🔧 Notas técnicas

- O cruzamento `Edifícios_Câmara.csv` ↔ PTD é feito com `geopandas.sjoin` (predicado `within`); pontos fora dos polígonos usam `sjoin_nearest` como *fallback*.
- O `ptd_id` é convertido para `string` em ambos os ficheiros antes do merge, para evitar incompatibilidades de tipo entre o `.gpkg` e os `.csv`.
- Indicadores económicos em falta (`val_eur`, `tir_pct`, `payback_anos`) ficam como `NaN` — não são forçados a zero, para não distorcer os gráficos e médias.
- O número de painéis (`total_paineis_reais`) é sempre arredondado a inteiro antes de qualquer cálculo ou visualização.
- **Cor do mapa = viabilidade:** PTDs com VAL > 0 ficam em tons de verde; VAL ≤ 0 ou sem dados em laranja; sem painéis instaláveis em cinzento.
- Os rótulos mostram `PTD {id} — {zona}` quando o `Ptd_zonas.csv` está disponível.
- PTDs com edifícios da câmara podem mostrar 0 painéis: a seleção é geográfica (área de serviço), mas o potencial fotovoltaico vem de um cálculo separado sobre edifícios residenciais. Isto é explicado diretamente na interface.
