# -*- coding: utf-8 -*-
"""
Dashboard CER Aveiro — Comunidades de Energia Renovável
Análise de viabilidade técnica e económica por PTD (Posto de Transformação e Distribuição)

Autoras: Carolina Raposo · Gabriela Silva · Rebeca Freitas

Ficheiros necessários na mesma pasta deste app.py:
    - VoronoiPTD_Areas_Servico_Rede.gpkg   (geometria dos PTDs: fid, ptd_id, n_nos, area_km2)
    - analise_economica_ptd.csv            (indicadores técnico-económicos por ptd_id, sep=";")
    - Edifícios_Câmara.csv                 (nome, latitude, longitude)
    - Ptd_zonas.csv                        (ptd_id, zona — nome da freguesia/zona de cada PTD)
    - ua.png, painel.png                   (opcionais, imagens da página de apresentação)
"""

import os
import re
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from folium import MacroElement
from jinja2 import Template
from streamlit_folium import st_folium
import plotly.express as px
from shapely.geometry import Point

# ─────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO GERAL DA PÁGINA
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CER Aveiro | Dashboard PTD",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────
# CAMINHOS DOS FICHEIROS (mesma pasta do app.py)
# ─────────────────────────────────────────────────────────────────────
VORONOI_GPKG   = "VoronoiPTD_Areas_Servico_Rede.gpkg"
ECONOMIA_CSV   = "analise_economica_ptd.csv"
CAMARA_CSV     = "Edifícios_Câmara.csv"
ZONAS_CSV      = "Ptd_zonas.csv"

# ─────────────────────────────────────────────────────────────────────
# CSS PERSONALIZADO
# ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .page-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #0B3D2E;
        margin-bottom: 0;
        line-height: 1.2;
    }
    .page-sub {
        font-size: 1.05rem;
        color: #44605A;
        margin-top: 0.2rem;
        margin-bottom: 0.4rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #0B3D2E 0%, #156450 100%);
        border-radius: 14px;
        padding: 18px 20px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 14px rgba(11,61,46,0.25);
        min-height: 108px;
        margin-bottom: 14px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        overflow-wrap: break-word;
        word-break: break-word;
    }
    .metric-card .big {
        font-size: 1.6rem;
        font-weight: 700;
        margin: 4px 0 0 0;
        line-height: 1.2;
        white-space: normal;
        max-width: 100%;
    }
    .metric-card .label {
        font-size: 0.82rem;
        opacity: 0.85;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        line-height: 1.3;
    }
    .section-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #0B3D2E;
        border-left: 5px solid #2E9E6B;
        padding-left: 10px;
        margin-top: 1.4rem;
        margin-bottom: 0.6rem;
    }
    .municipal-badge {
        background-color: #FFD166;
        color: #3A2E00;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .intro-text {
        font-size: 1.0rem;
        line-height: 1.65;
        color: #2B2B2B;
    }
    .panel-card {
        background: #F7FAF8;
        border: 1px solid #DCEAE3;
        border-radius: 16px;
        padding: 22px 26px;
        margin-top: 0.8rem;
        margin-bottom: 0.4rem;
    }
    .panel-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0B3D2E;
        margin-bottom: 0.5rem;
    }
    .panel-card-text {
        font-size: 0.95rem;
        line-height: 1.6;
        color: #3A4A45;
    }
    .panel-spec-badge {
        display: inline-block;
        background-color: #E3F1EA;
        color: #0B3D2E;
        padding: 3px 11px;
        border-radius: 14px;
        font-size: 0.78rem;
        font-weight: 600;
        margin: 2px 5px 2px 0;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# FUNÇÕES DE CARREGAMENTO DE DADOS (cacheadas)
# ─────────────────────────────────────────────────────────────────────

def corrigir_mojibake(texto):
    """
    Corrige texto com 'mojibake' — bytes UTF-8 que foram decodificados incorretamente
    como Latin-1/CP1252 algures no pipeline de origem dos CSVs (ex.: "GlÃ³ria" em vez
    de "Glória"). Deteta a assinatura típica desse erro (sequências de caracteres C1/
    Latin-1 sucessivos, como 'Ã' + caráter de continuação) e tenta reverter a dupla
    codificação. Texto já correto não é alterado.
    """
    if not isinstance(texto, str):
        return texto
    if re.search(r"[\u0080-\u00BF\u00C2\u00C3][\u0080-\u00BF]", texto):
        try:
            return texto.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return texto
    return texto


@st.cache_data(show_spinner=False)
def carregar_economia(caminho: str) -> pd.DataFrame:
    """Lê o CSV de indicadores económicos por PTD."""
    if not os.path.exists(caminho):
        return None
    # tenta separador ; primeiro (formato exportado pelos notebooks), depois ,
    try:
        df = pd.read_csv(caminho, sep=";", encoding="utf-8-sig")
        if df.shape[1] == 1:
            df = pd.read_csv(caminho, sep=",", encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(caminho, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    return df


@st.cache_data(show_spinner=False)
def carregar_voronoi(caminho: str) -> gpd.GeoDataFrame:
    """Lê a geometria dos PTDs (Voronoi de rede)."""
    if not os.path.exists(caminho):
        return None
    gdf = gpd.read_file(caminho)
    gdf.columns = [c.strip() for c in gdf.columns]
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=3763)  # ETRS89 / PT-TM06 (comum em dados PT) como fallback
    return gdf


@st.cache_data(show_spinner=False)
def carregar_camara(caminho: str) -> pd.DataFrame:
    """Lê a lista de edifícios da câmara (nome, latitude, longitude).
    Tenta várias combinações de encoding/separador antes de desistir, porque
    ficheiros exportados do Excel/Sheets em PT-PT podem vir em utf-8, utf-8-sig
    ou latin-1, com separador ',' ou ';', e nomes com vírgulas entre aspas
    (ex.: "Escola E B 1, 2 e 3 De São Bernardo") — o parser do pandas já lida
    bem com isto desde que o encoding esteja correto."""
    if not os.path.exists(caminho):
        return None

    tentativas = [
        dict(encoding="utf-8-sig", sep=","),
        dict(encoding="utf-8", sep=","),
        dict(encoding="latin-1", sep=","),
        dict(encoding="cp1252", sep=","),
        dict(encoding="utf-8-sig", sep=";"),
        dict(encoding="latin-1", sep=";"),
    ]
    df = None
    for kwargs in tentativas:
        try:
            tentativa = pd.read_csv(caminho, **kwargs, engine="python", on_bad_lines="skip")
            # válido só se tiver pelo menos 2 colunas reconhecíveis (nome + lat/lon)
            if tentativa.shape[1] >= 2:
                df = tentativa
                break
        except Exception:
            continue

    if df is None:
        return None

    df.columns = [c.strip().lower() for c in df.columns]
    # normalizar nomes de colunas possíveis
    ren = {}
    for c in df.columns:
        if c in ("lat", "latitude"):
            ren[c] = "latitude"
        elif c in ("lon", "lng", "longitude"):
            ren[c] = "longitude"
        elif c in ("nome", "name"):
            ren[c] = "nome"
    df = df.rename(columns=ren)
    if "latitude" not in df.columns or "longitude" not in df.columns:
        return None
    df = df.dropna(subset=["latitude", "longitude"])
    # corrige nomes com mojibake (ex.: "BibliotÃ©ca" → "Biblioteca")
    if "nome" in df.columns:
        df["nome"] = df["nome"].apply(corrigir_mojibake)
    return df


@st.cache_data(show_spinner=False)
def carregar_zonas(caminho: str) -> pd.DataFrame:
    """Lê o CSV com o nome da zona/freguesia de cada PTD (colunas: ptd_id, zona)."""
    if not os.path.exists(caminho):
        return None
    try:
        df = pd.read_csv(caminho, encoding="utf-8-sig")
        if df.shape[1] == 1:
            df = pd.read_csv(caminho, sep=";", encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(caminho, encoding="latin-1")
    df.columns = df.columns.str.strip().str.lower()
    df["ptd_id"] = df["ptd_id"].astype(str)
    # corrige nomes de zona com mojibake (ex.: "GlÃ³ria" → "Glória"), independentemente
    # de qual dos dois encodings acima foi usado na leitura
    if "zona" in df.columns:
        df["zona"] = df["zona"].apply(corrigir_mojibake)
    return df


@st.cache_data(show_spinner=False)
def calcular_ptds_municipais(_gdf_voronoi: gpd.GeoDataFrame, _df_camara: pd.DataFrame):
    """
    Faz o spatial join dos pontos da câmara com os polígonos de Voronoi (PTDs)
    para descobrir quais PTDs servem edifícios municipais.
    Devolve um set de ptd_id e um DataFrame dos edifícios com o ptd_id atribuído.
    """
    if _gdf_voronoi is None or _df_camara is None or len(_df_camara) == 0:
        return set(), pd.DataFrame()

    gdf_pontos = gpd.GeoDataFrame(
        _df_camara.copy(),
        geometry=[Point(xy) for xy in zip(_df_camara["longitude"], _df_camara["latitude"])],
        crs="EPSG:4326",
    )
    gdf_pontos = gdf_pontos.to_crs(_gdf_voronoi.crs)

    join = gpd.sjoin(gdf_pontos, _gdf_voronoi[["ptd_id", "geometry"]], how="left", predicate="within")

    # fallback por proximidade para pontos que não caem em nenhum polígono
    sem_match = join[join["ptd_id"].isna()]
    if len(sem_match) > 0:
        pontos_sem_match = gdf_pontos.loc[sem_match.index]
        nearest = gpd.sjoin_nearest(
            pontos_sem_match, _gdf_voronoi[["ptd_id", "geometry"]], how="left", distance_col="dist_m"
        )
        join.loc[nearest.index, "ptd_id"] = nearest["ptd_id"]

    ptds_municipais = set(join["ptd_id"].dropna().unique())
    return ptds_municipais, join


def fmt_eur(valor):
    if pd.isna(valor):
        return "—"
    if abs(valor) >= 1e6:
        return f"{valor/1e6:,.2f} M€"
    if abs(valor) >= 1e3:
        return f"{valor/1e3:,.0f} k€"
    return f"{valor:,.0f} €"


def fmt_num(valor, dec=0):
    if pd.isna(valor):
        return "—"
    return f"{valor:,.{dec}f}".replace(",", " ")


def rotulo_ptd(row, com_zona=True):
    """Devolve um rótulo legível 'PTD {id} — {zona}' (ou só 'PTD {id}' se não houver zona).
    Evita duplicar o prefixo "PTD" caso o próprio ptd_id já o inclua (ex.: "PTD001")."""
    id_str = str(row["ptd_id"])
    base = id_str if id_str.upper().startswith("PTD") else f"PTD {id_str}"
    if com_zona and "zona" in row.index and pd.notna(row.get("zona")) and str(row.get("zona")).strip():
        return f"{base} — {row['zona']}"
    return base


def filtro_zona(gdf, key):
    """
    Multiselect de zona/freguesia, reutilizável em qualquer página.
    Devolve a lista de zonas escolhidas (vazia = sem filtro = mostra tudo).
    """
    zonas_disponiveis = sorted(gdf["zona"].dropna().unique().tolist())
    return st.multiselect(
        "Filtrar por zona / freguesia",
        options=zonas_disponiveis,
        default=[],
        help="Deixa em branco para mostrar todas as zonas.",
        key=key,
    )


def aplicar_filtro_zona(gdf, zonas_selecionadas):
    """Aplica o filtro de zona a um GeoDataFrame, se houver zonas selecionadas."""
    if zonas_selecionadas:
        return gdf[gdf["zona"].isin(zonas_selecionadas)].copy()
    return gdf.copy()


def comparador_ptds(gdf, key_prefix, colunas_extra=None):
    """
    Secção reutilizável de comparação lado a lado entre 2-3 PTDs.
    gdf: GeoDataFrame (ou subconjunto já filtrado) com a coluna 'rotulo' como rótulo de escolha.
    key_prefix: prefixo único para as keys dos widgets, para não colidir entre páginas.
    colunas_extra: lista opcional de (nome_coluna, rótulo, formatador) adicionais à comparação base.
    """
    st.markdown('<div class="section-title">⚖️ Comparador de PTDs</div>', unsafe_allow_html=True)
    st.caption("Seleciona 2 a 3 PTDs para comparar os indicadores lado a lado.")

    opcoes = gdf.sort_values("rotulo")["rotulo"].tolist()
    escolhidos = st.multiselect(
        "Escolher PTDs a comparar (2 a 3)",
        options=opcoes,
        max_selections=3,
        key=f"{key_prefix}_comparador",
    )

    if len(escolhidos) < 2:
        st.info("Seleciona pelo menos 2 PTDs para ver a comparação.")
        return

    sub = gdf[gdf["rotulo"].isin(escolhidos)].copy()
    sub["rotulo"] = pd.Categorical(sub["rotulo"], categories=escolhidos, ordered=True)
    sub = sub.sort_values("rotulo")

    linhas_base = [
        ("Zona / Freguesia", "zona", lambda v: str(v) if pd.notna(v) else "—"),
        ("Painéis instaláveis", "total_paineis_reais", lambda v: fmt_num(v)),
        ("Potência (kWp)", "potencia_real_kwp", lambda v: f"{v:,.1f}" if pd.notna(v) else "—"),
        ("Produção anual (MWh)", "producao_real_mwh_ano", lambda v: f"{v:,.1f}" if pd.notna(v) else "—"),
        ("Consumo anual (kWh)", "consumo_anual_kwh", lambda v: f"{v:,.0f}" if pd.notna(v) and v > 0 else "—"),
        ("Autoconsumo (kWh/ano)", "autoconsumo_kwh", lambda v: f"{v:,.0f}" if pd.notna(v) and v > 0 else "—"),
        ("Excedente p/ rede (kWh/ano)", "excedente_kwh", lambda v: f"{v:,.0f}" if pd.notna(v) and v > 0 else "—"),
        ("Poupança ano 1", "poupanca_ano1_eur", lambda v: fmt_eur(v)),
        ("Investimento", "custo_instalacao_eur", lambda v: fmt_eur(v)),
        ("VAL", "val_eur", lambda v: fmt_eur(v)),
        ("TIR", "tir_pct", lambda v: f"{v:.1f}%" if pd.notna(v) else "—"),
        ("Payback", "payback_anos", lambda v: f"{v:.1f} anos" if pd.notna(v) else "—"),
        ("Rácio Produção/Consumo", "racio_producao_consumo", lambda v: f"{v:.2f}" if pd.notna(v) else "—"),
        ("Viável (VAL > 0)", "viavel", lambda v: "✅ Sim" if v else "⚠️ Não"),
    ]
    if colunas_extra:
        linhas_base.extend(colunas_extra)

    colunas_existentes = [c for c in sub.columns]
    linhas_base = [l for l in linhas_base if l[1] in colunas_existentes]

    tabela = pd.DataFrame(
        {
            row["rotulo"]: [fmt(row.get(col)) for _, col, fmt in linhas_base]
            for _, row in sub.iterrows()
        },
        index=[label for label, _, _ in linhas_base],
    )
    st.dataframe(tabela, use_container_width=True)

    # gráfico comparativo simples para os indicadores numéricos mais relevantes
    metricas_grafico = [
        ("total_paineis_reais", "Painéis instaláveis"),
        ("payback_anos", "Payback (anos)"),
        ("racio_producao_consumo", "Rácio Produção/Consumo"),
    ]
    metricas_grafico = [(c, l) for c, l in metricas_grafico if c in sub.columns]
    if metricas_grafico:
        g_cols = st.columns(len(metricas_grafico))
        for (col, label), g in zip(metricas_grafico, g_cols):
            fig = px.bar(
                sub, x="rotulo", y=col, title=label,
                labels={"rotulo": "", col: label},
                color="rotulo", color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig.update_layout(
                height=320, showlegend=False, margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(tickfont=dict(size=10)),
            )
            g.plotly_chart(fig, use_container_width=True)


def adicionar_legenda(mapa, titulo, itens):
    """
    Adiciona uma legenda fixa (canto inferior direito) a um mapa Folium.
    itens: lista de tuplos (cor_hex, texto).
    """
    linhas = "".join(
        f'<div style="display:flex;align-items:center;margin:3px 0;">'
        f'<span style="width:14px;height:14px;border-radius:3px;background:{cor};'
        f'display:inline-block;margin-right:7px;border:1px solid #999;"></span>'
        f'<span style="font-size:12.5px;color:#222;">{texto}</span></div>'
        for cor, texto in itens
    )
    legenda_html = f"""
    {{% macro html(this, kwargs) %}}
    <div style="
        position: fixed;
        bottom: 30px; right: 30px;
        z-index: 9999;
        background: white;
        padding: 12px 14px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.25);
        font-family: sans-serif;
        ">
        <div style="font-weight:700;font-size:13px;margin-bottom:6px;color:#0B3D2E;">{titulo}</div>
        {linhas}
    </div>
    {{% endmacro %}}
    """
    legenda = MacroElement()
    legenda._template = Template(legenda_html)
    mapa.get_root().add_child(legenda)


# ─────────────────────────────────────────────────────────────────────
# CARREGAR DADOS
# ─────────────────────────────────────────────────────────────────────
df_eco       = carregar_economia(ECONOMIA_CSV)
gdf_voronoi  = carregar_voronoi(VORONOI_GPKG)
df_camara    = carregar_camara(CAMARA_CSV)
df_zonas     = carregar_zonas(ZONAS_CSV)

dados_ok = df_eco is not None and gdf_voronoi is not None

if dados_ok:
    # normalizar tipo de ptd_id em ambos para garantir merge correto
    gdf_voronoi["ptd_id"] = gdf_voronoi["ptd_id"].astype(str)
    df_eco["ptd_id"] = df_eco["ptd_id"].astype(str)
    # gdf_voronoi já fica com ptd_id em string a partir daqui — usado também
    # no spatial join de calcular_ptds_municipais, garantindo tipos consistentes
    # com gdf_mapa_4326["ptd_id"] (igualmente string) na chamada .isin() mais abaixo

    gdf_mapa = gdf_voronoi.merge(df_eco, on="ptd_id", how="left")

    # garantir colunas-chave mesmo que faltem no CSV (evita KeyError no resto da app)
    for col, default in [
        ("total_paineis_reais", 0), ("potencia_real_kwp", 0), ("producao_real_mwh_ano", 0),
        ("custo_instalacao_eur", 0), ("payback_anos", float("nan")), ("val_eur", float("nan")),
        ("tir_pct", float("nan")), ("racio_autossuficiencia", float("nan")),
        ("consumo_anual_kwh", 0), ("autoconsumo_kwh", 0), ("excedente_kwh", 0),
        ("poupanca_ano1_eur", 0), ("n_cp7_com_consumo", 0),
    ]:
        if col not in gdf_mapa.columns:
            gdf_mapa[col] = default
        elif not pd.isna(default):
            # só preenche com 0 as colunas numéricas onde "sem PTD correspondente" = "sem painéis/custo".
            # Indicadores económicos (val_eur, tir_pct, payback_anos, racio_autossuficiencia) ficam
            # como NaN quando não há dados, em vez de serem forçados a 0 (o que distorceria os gráficos).
            gdf_mapa[col] = gdf_mapa[col].fillna(default)

    # CORREÇÃO: número de painéis tem de ser inteiro (não pode existir "1.36 painéis").
    # O ficheiro de origem já aplica floor por edifício, mas o merge/groupby pode devolver
    # float (ex.: 0.0, soma de inteiros como float64) — forçamos o arredondamento aqui
    # como salvaguarda final antes de qualquer cálculo ou visualização.
    gdf_mapa["total_paineis_reais"] = gdf_mapa["total_paineis_reais"].round(0).astype(int)

    # juntar o nome da zona/freguesia de cada PTD (Ptd_zonas.csv: ptd_id, zona)
    if df_zonas is not None:
        gdf_mapa = gdf_mapa.merge(df_zonas[["ptd_id", "zona"]], on="ptd_id", how="left")
        gdf_mapa["zona"] = gdf_mapa["zona"].fillna("Zona desconhecida")
    else:
        gdf_mapa["zona"] = "Zona desconhecida"

    # rótulo combinado usado em mapas, popups e eixos dos gráficos
    gdf_mapa["rotulo"] = gdf_mapa.apply(rotulo_ptd, axis=1)

    # PTD "viável" = VAL positivo (critério usado para destacar no mapa com cor mais escura)
    gdf_mapa["viavel"] = gdf_mapa["val_eur"] > 0

    # Rácio Produção / Consumo (CER): vem diretamente do notebook de análise económica
    # (coluna 'racio_autossuficiencia', já calculada como produção_kwh / consumo_kwh, com NaN
    # quando não há consumo registado). Mantemos o nome 'racio_producao_consumo' usado no resto
    # do dashboard, mas a fonte de verdade passa a ser sempre o CSV — evita o app e o notebook
    # divergirem se a fórmula for ajustada numa próxima versão.
    if "racio_autossuficiencia" in gdf_mapa.columns:
        gdf_mapa["racio_producao_consumo"] = gdf_mapa["racio_autossuficiencia"]
    else:
        consumo_kwh = gdf_mapa["consumo_anual_kwh"].replace(0, np.nan)
        producao_kwh = gdf_mapa["producao_real_mwh_ano"] * 1000
        gdf_mapa["racio_producao_consumo"] = producao_kwh / consumo_kwh

    gdf_mapa_4326 = gdf_mapa.to_crs(epsg=4326)

    # PTDs com edifícios municipais
    ptds_municipais, camara_join = calcular_ptds_municipais(gdf_voronoi, df_camara)
    gdf_mapa_4326["is_municipal"] = gdf_mapa_4326["ptd_id"].isin(ptds_municipais)

# ─────────────────────────────────────────────────────────────────────
# BARRA LATERAL — NAVEGAÇÃO
# ─────────────────────────────────────────────────────────────────────
st.sidebar.markdown("### ☀️ CER Aveiro")
pagina = st.sidebar.radio(
    "Navegação",
    [
        "🏠 Apresentação",
        "🗺️ Mapa Geral — Todos os PTDs",
        "🏛️ Mapa — PTDs com Edifícios da Câmara",
        "⚖️ Mapa — Rácio Produção/Consumo (CER)",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small>Fontes: E-Redes (2024–2025), PVGIS, cartografia municipal de edifícios, "
    "rede de Voronoi (OSMnx).</small>",
    unsafe_allow_html=True,
)

if not dados_ok:
    st.sidebar.error(
        "⚠️ Não foi possível carregar os ficheiros principais.\n\n"
        f"Verifica se **{VORONOI_GPKG}** e **{ECONOMIA_CSV}** estão na mesma pasta do `app.py`."
    )

if df_zonas is None:
    st.sidebar.warning(
        f"⚠️ Ficheiro **{ZONAS_CSV}** não encontrado — todos os PTDs vão aparecer como "
        "'Zona desconhecida'. Verifica o nome exato do ficheiro na pasta do `app.py`."
    )
if df_camara is None:
    st.sidebar.warning(
        f"⚠️ Ficheiro **{CAMARA_CSV}** não encontrado — a página de Edifícios da Câmara "
        "não vai funcionar."
    )

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 1 — APRESENTAÇÃO
# ═══════════════════════════════════════════════════════════════════
if pagina == "🏠 Apresentação":

    col_logo, col_titulo = st.columns([1, 5])
    with col_logo:
        if os.path.exists("ua.png"):
            st.image("ua.png", width=110)
        else:
            st.markdown("# 🎓")
    with col_titulo:
        st.markdown('<p class="page-title">Comunidades de Energia Renovável — Aveiro</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="page-sub">Análise de viabilidade técnica e económica por Posto de '
            'Transformação e Distribuição (PTD)</p>',
            unsafe_allow_html=True,
        )
        st.markdown("<small>Carolina Raposo&nbsp;&nbsp;·&nbsp;&nbsp;Gabriela Silva&nbsp;&nbsp;"
                     "·&nbsp;&nbsp;Rebeca Freitas</small>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Objetivo do trabalho</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="intro-text">
Este trabalho, desenvolvido no âmbito de uma unidade curricular da Universidade de Aveiro,
tem como objetivo avaliar a <b>viabilidade técnica e económica da implementação de
Comunidades de Energia Renovável (CER)</b> no município de Aveiro. Uma CER permite que um
conjunto de consumidores e produtores, ligados ao mesmo Posto de Transformação e Distribuição
(PTD), partilhem entre si a energia produzida localmente através de painéis fotovoltaicos
instalados nos telhados dos edifícios da zona — reduzindo a fatura energética dos participantes
e promovendo a descarbonização da rede elétrica a nível local.
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="section-title">O que foi feito</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="intro-text">
Partindo de dados reais de consumo elétrico da E-Redes (2024–2025), de irradiância solar do
PVGIS e de cartografia de edifícios do município, foi construído um pipeline de análise que,
para cada PTD de Aveiro: (1) estima o <b>potencial fotovoltaico</b> instalável em cada telhado;
(2) atribui cada edifício à sua área de serviço de rede através de uma tesselação de Voronoi;
e (3) calcula os indicadores de <b>viabilidade económica</b> — investimento, VAL, TIR e
payback — para cada cenário de instalação. Os resultados são apresentados neste dashboard
interativo, que permite explorar o mapa de PTDs, comparar os PTDs com maior potencial e
investigar o cenário específico dos edifícios municipais da Câmara de Aveiro, bem como o
rácio entre produção fotovoltaica e consumo elétrico em cada zona.
</div>
""", unsafe_allow_html=True)

    if os.path.exists("painel.png"):
        st.markdown('<div class="section-title">O painel fotovoltaico utilizado na análise</div>', unsafe_allow_html=True)
        col_texto, col_img = st.columns([3, 2])
        with col_texto:
            st.markdown("""
<div class="panel-card">
    <div class="panel-card-title">Painel monocristalino de 450 Wp</div>
    <div class="panel-card-text">
        Todas as estimativas de produção fotovoltaica e de número de painéis instaláveis
        apresentadas neste dashboard foram calculadas com base num <b>painel monocristalino
        de 450 Wp</b> com cerca de 2 m² de área — uma escolha representativa da tecnologia
        residencial/comercial atualmente mais comum em Portugal, que combina boa eficiência
        de conversão com um custo por Watt competitivo. Esta referência foi usada para
        converter a área de telhado útil de cada edifício em número de painéis e em
        potência instalável (kWp), servindo de base a todos os cálculos de investimento,
        produção anual e indicadores económicos (VAL, TIR, payback) presentes nas páginas
        seguintes.
    </div>
    <div style="margin-top:12px;">
        <span class="panel-spec-badge">450 Wp</span>
        <span class="panel-spec-badge">Monocristalino</span>
        <span class="panel-spec-badge">≈ 2 m² / painel</span>
        <span class="panel-spec-badge">Fator de empacotamento 0,85</span>
    </div>
</div>
""", unsafe_allow_html=True)
        with col_img:
            st.image("painel.png", caption="Painel fotovoltaico monocristalino (450 Wp | 2 m²)",
                      use_container_width=True)

    st.markdown('<div class="section-title">Metodologia em síntese</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
**1. Potencial Fotovoltaico**
Cálculo da área de telhado útil por edifício (cartografia + código postal),
cruzada com a irradiância PVGIS (H(i) anual ≈ 1.860 kWh/m²/ano) para
estimar a produção fotovoltaica teórica.
""")
    with c2:
        st.markdown("""
**2. Roteamento à Rede**
Cada edifício é atribuído ao seu PTD através de uma tesselação de **Voronoi
de rede** (distâncias reais de rua via OSMnx), e o número de painéis
instaláveis é limitado por um fator de empacotamento físico (0,85) e pela
potência elétrica do telhado.
""")
    with c3:
        st.markdown("""
**3. Viabilidade Económica**
Investimento de **1.200 €/painel**. Para cada PTD, distingue-se autoconsumo
(0,25 €/kWh) de excedente injetado na rede (tarifa RESP, 0,05 €/kWh),
calculando VAL, TIR e *payback* a 25 anos com 7% de taxa de desconto e
0,5%/ano de degradação dos painéis.
""")

    st.markdown('<div class="section-title">Indicadores globais do município</div>', unsafe_allow_html=True)
    if dados_ok:
        total_paineis  = gdf_mapa_4326["total_paineis_reais"].sum()
        total_potencia = gdf_mapa_4326["potencia_real_kwp"].sum() / 1000
        total_custo    = gdf_mapa_4326["custo_instalacao_eur"].sum()
        n_ptds         = gdf_mapa_4326["ptd_id"].nunique()
        n_ptds_camara  = gdf_mapa_4326["is_municipal"].sum()

        m1, m2, m3, m4, m5 = st.columns(5)
        for col, label, val in zip(
            [m1, m2, m3, m4, m5],
            ["PTDs Analisados", "Painéis Instaláveis", "Potência Total", "Investimento Total", "PTDs com Edif. Câmara"],
            [fmt_num(n_ptds), fmt_num(total_paineis), f"{total_potencia:,.1f} MWp", fmt_eur(total_custo), fmt_num(n_ptds_camara)],
        ):
            with col:
                st.markdown(
                    f'<div class="metric-card"><div class="label">{label}</div>'
                    f'<div class="big">{val}</div></div>',
                    unsafe_allow_html=True,
                )

        total_producao  = gdf_mapa_4326["producao_real_mwh_ano"].sum() / 1000
        total_poupanca  = gdf_mapa_4326["poupanca_ano1_eur"].sum()
        n_ptds_viaveis  = gdf_mapa_4326["viavel"].sum()
        n_ptds_consumo  = (gdf_mapa_4326["consumo_anual_kwh"] > 0).sum()

        n1, n2, n3, n4 = st.columns(4)
        for col, label, val in zip(
            [n1, n2, n3, n4],
            ["Produção Total Estimada", "Poupança Total (ano 1)", "PTDs Viáveis (VAL > 0)", "PTDs com Consumo Emparelhado"],
            [f"{total_producao:,.1f} GWh", fmt_eur(total_poupanca), fmt_num(n_ptds_viaveis), fmt_num(n_ptds_consumo)],
        ):
            with col:
                st.markdown(
                    f'<div class="metric-card"><div class="label">{label}</div>'
                    f'<div class="big">{val}</div></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Carrega os ficheiros de dados para ver os indicadores globais.")

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 2 — MAPA GERAL (TODOS OS PTDs)
# ═══════════════════════════════════════════════════════════════════
elif pagina == "🗺️ Mapa Geral — Todos os PTDs":

    st.markdown('<p class="page-title">Mapa Interativo — Todos os PTDs</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">Número de painéis instaláveis, custo de investimento e payback '
        'por Posto de Transformação de Distribuição</p>',
        unsafe_allow_html=True,
    )

    if not dados_ok:
        st.error(f"Faltam ficheiros: **{VORONOI_GPKG}** e/ou **{ECONOMIA_CSV}**.")
    else:
        # ── Filtros ──
        with st.expander("🔍 Filtros", expanded=False):
            zonas_sel = filtro_zona(gdf_mapa_4326, key="geral_zona")
            fc1, fc2 = st.columns(2)
            with fc1:
                min_paineis = st.slider(
                    "Mínimo de painéis instaláveis", 0,
                    int(gdf_mapa_4326["total_paineis_reais"].max()) or 1, 0,
                )
            with fc2:
                so_viaveis = st.checkbox("Mostrar apenas PTDs com VAL > 0 (viáveis)", value=False)

        gdf_filtrado = aplicar_filtro_zona(gdf_mapa_4326, zonas_sel)
        gdf_filtrado = gdf_filtrado[gdf_filtrado["total_paineis_reais"] >= min_paineis].copy()
        if so_viaveis:
            gdf_filtrado = gdf_filtrado[gdf_filtrado["val_eur"] > 0]

        if len(gdf_filtrado) == 0:
            st.info("Nenhum PTD cumpre os filtros selecionados. Ajusta a zona ou os critérios acima.")
        else:
            # ── KPIs ──
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.markdown(
                    f'<div class="metric-card"><div class="label">PTDs no filtro</div>'
                    f'<div class="big">{fmt_num(gdf_filtrado["ptd_id"].nunique())}</div></div>',
                    unsafe_allow_html=True,
                )
            with k2:
                st.markdown(
                    f'<div class="metric-card"><div class="label">Painéis Totais</div>'
                    f'<div class="big">{fmt_num(gdf_filtrado["total_paineis_reais"].sum())}</div></div>',
                    unsafe_allow_html=True,
                )
            with k3:
                st.markdown(
                    f'<div class="metric-card"><div class="label">Investimento Total</div>'
                    f'<div class="big">{fmt_eur(gdf_filtrado["custo_instalacao_eur"].sum())}</div></div>',
                    unsafe_allow_html=True,
                )
            with k4:
                payback_medio = gdf_filtrado.loc[gdf_filtrado["payback_anos"].notna(), "payback_anos"].mean()
                st.markdown(
                    f'<div class="metric-card"><div class="label">Payback Médio</div>'
                    f'<div class="big">{payback_medio:,.1f} anos</div></div>'
                    if pd.notna(payback_medio) else
                    '<div class="metric-card"><div class="label">Payback Médio</div><div class="big">—</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="section-title">Mapa dos PTDs</div>', unsafe_allow_html=True)
            st.caption(
                "🟢 Tom mais escuro = PTD **viável** (VAL > 0 a 25 anos). 🔘 Cinzento = PTD sem painéis "
                "instaláveis ou sem dados de consumo emparelhados."
            )

            # ── Mapa Folium ──
            if len(gdf_filtrado) > 0:
                centro = [gdf_filtrado.geometry.centroid.y.mean(), gdf_filtrado.geometry.centroid.x.mean()]
            else:
                centro = [40.64, -8.65]  # Aveiro

            m = folium.Map(location=centro, zoom_start=13, tiles="CartoDB positron")

            max_paineis = gdf_filtrado["total_paineis_reais"].max() or 1

            def cor_por_viabilidade(row):
                """
                CORREÇÃO: a cor já não depende apenas da quantidade de painéis — depende
                principalmente da VIABILIDADE económica (VAL > 0), com o tom mais escuro
                reservado aos PTDs viáveis. Dentro de cada grupo (viável / não viável),
                a intensidade da cor ainda varia com o número de painéis, para distinguir
                os maiores potenciais dentro do mesmo grupo.
                """
                n = row["total_paineis_reais"]
                if n == 0:
                    return "#E5E5E5"  # cinzento — sem painéis instaláveis
                frac = n / max_paineis if max_paineis else 0
                if row["viavel"]:
                    # verde escuro — viável (VAL > 0); mais escuro quanto mais painéis
                    if frac > 0.5:
                        return "#0B3D2E"
                    return "#1E7A52"
                else:
                    # laranja claro — não viável (VAL <= 0 ou sem dados económicos)
                    if frac > 0.5:
                        return "#D98C3D"
                    return "#F2C18D"

            for _, row in gdf_filtrado.iterrows():
                payback_txt = f"{row['payback_anos']:.1f} anos" if pd.notna(row["payback_anos"]) else "—"
                val_txt = fmt_eur(row["val_eur"]) if pd.notna(row["val_eur"]) else "—"
                tir_txt = f"{row['tir_pct']:.1f}%" if pd.notna(row["tir_pct"]) else "—"
                viavel_txt = "✅ Viável" if row["viavel"] else "⚠️ Não viável / sem dados"
                consumo_txt = f"{row['consumo_anual_kwh']:,.0f} kWh" if pd.notna(row.get("consumo_anual_kwh")) and row.get("consumo_anual_kwh", 0) > 0 else "—"
                popup_html = f"""
                <b>{row['rotulo']}</b><br>
                <span style="font-size:11px;">{viavel_txt}</span><br><br>
                Painéis instaláveis: <b>{int(row['total_paineis_reais']):,}</b><br>
                Potência: {row['potencia_real_kwp']:.1f} kWp<br>
                Produção anual: <b>{row['producao_real_mwh_ano']:.1f} MWh</b><br>
                Consumo anual: <b>{consumo_txt}</b><br>
                Investimento: <b>{fmt_eur(row['custo_instalacao_eur'])}</b><br>
                VAL: {val_txt} &nbsp;|&nbsp; TIR: {tir_txt}<br>
                Payback: <b>{payback_txt}</b>
                """
                folium.GeoJson(
                    row.geometry.__geo_interface__,
                    style_function=lambda feat, color=cor_por_viabilidade(row): {
                        "fillColor": color, "color": "#3A3A3A", "weight": 0.6, "fillOpacity": 0.78,
                    },
                    tooltip=f"{row['rotulo']} · {int(row['total_paineis_reais'])} painéis",
                    popup=folium.Popup(popup_html, max_width=290),
                ).add_to(m)

            adicionar_legenda(m, "Legenda — Viabilidade (VAL)", [
                ("#0B3D2E", "Viável · muitos painéis"),
                ("#1E7A52", "Viável · poucos painéis"),
                ("#D98C3D", "Não viável · muitos painéis"),
                ("#F2C18D", "Não viável · poucos painéis"),
                ("#E5E5E5", "Sem painéis instaláveis"),
            ])

            st_folium(m, width=None, height=560, returned_objects=[])

            # ── Gráficos Top 10 ──
            st.markdown('<div class="section-title">Top 10 PTDs</div>', unsafe_allow_html=True)
            g1, g2 = st.columns(2)

            top10_paineis = gdf_filtrado.nlargest(10, "total_paineis_reais").sort_values("total_paineis_reais", ascending=False)
            fig1 = px.bar(
                top10_paineis, x="total_paineis_reais", y="rotulo", orientation="h",
                title="Top 10 — Painéis Instaláveis",
                labels={"total_paineis_reais": "Nº de painéis", "rotulo": ""},
                color="viavel", color_discrete_map={True: "#1E7A52", False: "#D98C3D"},
                text="total_paineis_reais",
                category_orders={"rotulo": top10_paineis["rotulo"].tolist()},
            )
            fig1.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
            fig1.update_layout(
                height=420, legend_title_text="Viável (VAL>0)", margin=dict(l=10, r=10, t=50, b=10),
                yaxis=dict(tickfont=dict(size=11)),
            )
            g1.plotly_chart(fig1, use_container_width=True)

            top10_custo = gdf_filtrado.nlargest(10, "custo_instalacao_eur").sort_values("custo_instalacao_eur", ascending=False)
            fig2 = px.bar(
                top10_custo, x="custo_instalacao_eur", y="rotulo", orientation="h",
                title="Top 10 — Custo de Investimento",
                labels={"custo_instalacao_eur": "Investimento (€)", "rotulo": ""},
                color="viavel", color_discrete_map={True: "#1E7A52", False: "#D98C3D"},
                text=top10_custo["custo_instalacao_eur"].apply(fmt_eur),
                category_orders={"rotulo": top10_custo["rotulo"].tolist()},
            )
            fig2.update_traces(textposition="outside", cliponaxis=False)
            fig2.update_layout(
                height=420, legend_title_text="Viável (VAL>0)", margin=dict(l=10, r=10, t=50, b=10),
                yaxis=dict(tickfont=dict(size=11)),
            )
            g2.plotly_chart(fig2, use_container_width=True)

            g3, g4 = st.columns(2)
            top10_payback = gdf_filtrado[gdf_filtrado["payback_anos"].notna()].nsmallest(10, "payback_anos") \
                .sort_values("payback_anos", ascending=False)
            fig3 = px.bar(
                top10_payback, x="payback_anos", y="rotulo", orientation="h",
                title="Top 10 — Menor Payback",
                labels={"payback_anos": "Anos até retorno", "rotulo": ""},
                color="payback_anos", color_continuous_scale="Greens_r",
                text=top10_payback["payback_anos"].round(1),
                category_orders={"rotulo": top10_payback["rotulo"].tolist()},
            )
            fig3.update_traces(textposition="outside", cliponaxis=False)
            fig3.update_layout(
                height=420, coloraxis_showscale=False, margin=dict(l=10, r=10, t=50, b=10),
                yaxis=dict(tickfont=dict(size=11)),
            )
            g3.plotly_chart(fig3, use_container_width=True)

            top10_val = gdf_filtrado[gdf_filtrado["val_eur"].notna()].nlargest(10, "val_eur") \
                .sort_values("val_eur", ascending=False)
            fig4 = px.bar(
                top10_val, x="val_eur", y="rotulo", orientation="h",
                title="Top 10 — Maior VAL (Valor Atual Líquido)",
                labels={"val_eur": "VAL (€)", "rotulo": ""},
                color="val_eur", color_continuous_scale="Greens",
                text=top10_val["val_eur"].apply(fmt_eur),
                category_orders={"rotulo": top10_val["rotulo"].tolist()},
            )
            fig4.update_traces(textposition="outside", cliponaxis=False)
            fig4.update_layout(
                height=420, coloraxis_showscale=False, margin=dict(l=10, r=10, t=50, b=10),
                yaxis=dict(tickfont=dict(size=11)),
            )
            g4.plotly_chart(fig4, use_container_width=True)

            with st.expander("📋 Ver tabela de dados completa"):
                colunas_tabela = [c for c in [
                    "ptd_id", "zona", "total_paineis_reais", "potencia_real_kwp", "producao_real_mwh_ano",
                    "custo_instalacao_eur", "val_eur", "tir_pct", "payback_anos", "racio_autossuficiencia",
                    "viavel", "is_municipal",
                ] if c in gdf_filtrado.columns]
                st.dataframe(
                    gdf_filtrado[colunas_tabela].sort_values("total_paineis_reais", ascending=False),
                    use_container_width=True, hide_index=True,
                )

            st.divider()
            comparador_ptds(gdf_filtrado, key_prefix="geral")

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 3 — MAPA PTDs COM EDIFÍCIOS DA CÂMARA
# ═══════════════════════════════════════════════════════════════════
elif pagina == "🏛️ Mapa — PTDs com Edifícios da Câmara":

    st.markdown('<p class="page-title">Mapa Interativo — PTDs com Edifícios Municipais</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">Cenário exclusivo: apenas os PTDs cuja área de serviço contém '
        'edifícios da Câmara Municipal de Aveiro</p>',
        unsafe_allow_html=True,
    )

    if not dados_ok:
        st.error(f"Faltam ficheiros: **{VORONOI_GPKG}** e/ou **{ECONOMIA_CSV}**.")
    elif df_camara is None:
        st.error(f"Não foi possível carregar **{CAMARA_CSV}**. Verifica se o ficheiro está na pasta do app.")
    else:
        gdf_camara_ptds = gdf_mapa_4326[gdf_mapa_4326["is_municipal"]].copy()

        if len(gdf_camara_ptds) == 0:
            st.warning(
                "Nenhum PTD foi associado a edifícios da câmara. Verifica as coordenadas em "
                f"**{CAMARA_CSV}** ou o sistema de coordenadas do **{VORONOI_GPKG}**."
            )
        else:
            n_zero = (gdf_camara_ptds["total_paineis_reais"] == 0).sum()

            # ── Explicação: porque é que alguns PTDs aqui mostram 0 painéis ──
            with st.expander(
                f"ℹ️ Porque é que {n_zero} destes PTDs mostram 0 painéis instaláveis?",
                expanded=(n_zero > 0),
            ):
                st.markdown("""
Este mapa mostra os PTDs cuja **área de serviço (polígono de Voronoi)** contém pelo
menos um edifício da Câmara — ou seja, o critério de seleção é **geográfico**
(o edifício municipal está dentro daquela área), não é o próprio edifício da câmara
a gerar os painéis.

O número de painéis de cada PTD vem de um cálculo **separado**: a soma do potencial
fotovoltaico de todos os **edifícios residenciais/CP7 com dados de consumo da E-Redes**
mapeados para esse PTD (ficheiro `analise_economica_ptd.csv`). Um PTD pode aparecer
aqui com **0 painéis** por uma ou mais destas razões:

1. **O edifício da câmara não tem área de telhado suficiente** após aplicar o fator de
   empacotamento (0,85) e a restrição de potência — o `floor()` físico chega a zero painéis
   inteiros para telhados pequenos ou muito fragmentados.
2. **A área de serviço daquele PTD não tem outros edifícios residenciais associados** com
   dados de consumo válidos da E-Redes (CP7 emparelhado), pelo que o agregado do PTD fica
   em zero mesmo que o edifício da câmara exista fisicamente ali.
3. **O próprio edifício da câmara pode não estar incluído no cálculo de potencial** — o
   pipeline de produção fotovoltaica baseia-se na cartografia de edifícios por código
   postal (CP7), e edifícios públicos/institucionais por vezes não têm a mesma cobertura
   de dados de consumo que os residenciais (ver limitação dos "Grandes Consumidores" nos
   notebooks de origem).

Em resumo: **"0 painéis" não significa erro** — significa que, com os dados atualmente
disponíveis, não há potencial fotovoltaico residencial estimado dentro da área de serviço
desse PTD específico, ainda que ele sirva um edifício da câmara.
""")

            # ── Filtros ──
            with st.expander("🔍 Filtros", expanded=False):
                zonas_sel_camara = filtro_zona(gdf_camara_ptds, key="camara_zona")
                fcc1, fcc2 = st.columns(2)
                with fcc1:
                    min_paineis_camara = st.slider(
                        "Mínimo de painéis instaláveis", 0,
                        int(gdf_camara_ptds["total_paineis_reais"].max()) or 1, 0,
                        key="camara_min_paineis",
                    )
                with fcc2:
                    so_viaveis_camara = st.checkbox(
                        "Mostrar apenas PTDs com VAL > 0 (viáveis)", value=False, key="camara_so_viaveis"
                    )

            gdf_camara_filtrado = aplicar_filtro_zona(gdf_camara_ptds, zonas_sel_camara)
            gdf_camara_filtrado = gdf_camara_filtrado[
                gdf_camara_filtrado["total_paineis_reais"] >= min_paineis_camara
            ].copy()
            if so_viaveis_camara:
                gdf_camara_filtrado = gdf_camara_filtrado[gdf_camara_filtrado["val_eur"] > 0]

            if len(gdf_camara_filtrado) == 0:
                st.info("Nenhum PTD cumpre os filtros selecionados. Ajusta a zona ou os critérios acima.")
            else:
                gdf_camara_ptds = gdf_camara_filtrado

                # ── KPIs ──
                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    st.markdown(
                        f'<div class="metric-card"><div class="label">PTDs com Edif. Câmara</div>'
                        f'<div class="big">{fmt_num(gdf_camara_ptds["ptd_id"].nunique())}</div></div>',
                        unsafe_allow_html=True,
                    )
                with k2:
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Painéis Totais</div>'
                        f'<div class="big">{fmt_num(gdf_camara_ptds["total_paineis_reais"].sum())}</div></div>',
                        unsafe_allow_html=True,
                    )
                with k3:
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Investimento Total</div>'
                        f'<div class="big">{fmt_eur(gdf_camara_ptds["custo_instalacao_eur"].sum())}</div></div>',
                        unsafe_allow_html=True,
                    )
                with k4:
                    payback_medio = gdf_camara_ptds.loc[gdf_camara_ptds["payback_anos"].notna(), "payback_anos"].mean()
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Payback Médio</div>'
                        f'<div class="big">{payback_medio:,.1f} anos</div></div>'
                        if pd.notna(payback_medio) else
                        '<div class="metric-card"><div class="label">Payback Médio</div><div class="big">—</div></div>',
                        unsafe_allow_html=True,
                    )

                st.markdown('<div class="section-title">Mapa dos PTDs com edifícios municipais</div>', unsafe_allow_html=True)
                st.caption(
                    "🟢 Tom mais escuro = PTD **viável** (VAL > 0). 🔘 Cinzento = sem painéis instaláveis "
                    "(ver explicação acima). Pontos verde-escuro = localização dos edifícios da câmara."
                )

                centro = [gdf_camara_ptds.geometry.centroid.y.mean(), gdf_camara_ptds.geometry.centroid.x.mean()]
                m2 = folium.Map(location=centro, zoom_start=14, tiles="CartoDB positron")

                max_paineis_cam = gdf_camara_ptds["total_paineis_reais"].max() or 1

                def cor_por_viabilidade_camara(row):
                    n = row["total_paineis_reais"]
                    if n == 0:
                        return "#E5E5E5"
                    frac = n / max_paineis_cam if max_paineis_cam else 0
                    if row["viavel"]:
                        return "#0B3D2E" if frac > 0.5 else "#1E7A52"
                    return "#D98C3D" if frac > 0.5 else "#F2C18D"

                for _, row in gdf_camara_ptds.iterrows():
                    payback_txt = f"{row['payback_anos']:.1f} anos" if pd.notna(row["payback_anos"]) else "—"
                    val_txt = fmt_eur(row["val_eur"]) if pd.notna(row["val_eur"]) else "—"
                    viavel_txt = "✅ Viável" if row["viavel"] else "⚠️ Não viável / sem dados"
                    consumo_txt = f"{row['consumo_anual_kwh']:,.0f} kWh" if pd.notna(row.get("consumo_anual_kwh")) and row.get("consumo_anual_kwh", 0) > 0 else "—"
                    aviso_zero = (
                        "<br><span style='color:#A65300;font-size:11px;'>⚠️ 0 painéis — ver explicação "
                        "no topo da página</span>" if row["total_paineis_reais"] == 0 else ""
                    )
                    popup_html = f"""
                    <b>{row['rotulo']}</b>
                    <span style="background:#FFD166;padding:1px 6px;border-radius:8px;font-size:11px;">
                    edif. câmara</span><br>
                    <span style="font-size:11px;">{viavel_txt}</span><br><br>
                    Painéis instaláveis: <b>{int(row['total_paineis_reais']):,}</b>{aviso_zero}<br>
                    Potência: {row['potencia_real_kwp']:.1f} kWp<br>
                    Produção anual: <b>{row['producao_real_mwh_ano']:.1f} MWh</b><br>
                    Consumo anual: <b>{consumo_txt}</b><br>
                    Investimento: <b>{fmt_eur(row['custo_instalacao_eur'])}</b><br>
                    VAL: {val_txt}<br>
                    Payback: <b>{payback_txt}</b>
                    """
                    folium.GeoJson(
                        row.geometry.__geo_interface__,
                        style_function=lambda feat, color=cor_por_viabilidade_camara(row): {
                            "fillColor": color, "color": "#3A2E00", "weight": 1.0, "fillOpacity": 0.72,
                        },
                        tooltip=f"{row['rotulo']} · {int(row['total_paineis_reais'])} painéis",
                        popup=folium.Popup(popup_html, max_width=290),
                    ).add_to(m2)

                # marcar também os pontos dos edifícios da câmara
                for _, ed in df_camara.iterrows():
                    folium.CircleMarker(
                        location=[ed["latitude"], ed["longitude"]],
                        radius=5, color="#0B3D2E", fill=True, fill_color="#0B3D2E", fill_opacity=0.9,
                        tooltip=ed.get("nome", "Edifício da Câmara"),
                    ).add_to(m2)

                adicionar_legenda(m2, "Legenda", [
                    ("#0B3D2E", "Viável · muitos painéis"),
                    ("#1E7A52", "Viável · poucos painéis"),
                    ("#D98C3D", "Não viável · muitos painéis"),
                    ("#F2C18D", "Não viável · poucos painéis"),
                    ("#E5E5E5", "Sem painéis instaláveis"),
                ])

                st_folium(m2, width=None, height=560, returned_objects=[])

                # ── Gráfico Top 10 ──
                st.markdown('<div class="section-title">Top 10 PTDs (Edifícios da Câmara)</div>', unsafe_allow_html=True)
                top10_camara = gdf_camara_ptds.nlargest(10, "total_paineis_reais").sort_values("total_paineis_reais", ascending=False)
                if top10_camara["total_paineis_reais"].sum() == 0:
                    st.info("Todos os PTDs com edifícios da câmara têm 0 painéis instaláveis — ver explicação acima.")
                else:
                    fig5 = px.bar(
                        top10_camara, x="total_paineis_reais", y="rotulo", orientation="h",
                        title="Top 10 — Painéis Instaláveis (PTDs com Edifícios da Câmara)",
                        labels={"total_paineis_reais": "Nº de painéis", "rotulo": ""},
                        color="viavel", color_discrete_map={True: "#1E7A52", False: "#D98C3D"},
                        text="total_paineis_reais",
                        category_orders={"rotulo": top10_camara["rotulo"].tolist()},
                    )
                    fig5.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
                    fig5.update_layout(
                        height=440, legend_title_text="Viável (VAL>0)", margin=dict(l=10, r=10, t=50, b=10),
                        yaxis=dict(tickfont=dict(size=11)),
                    )
                    st.plotly_chart(fig5, use_container_width=True)

                with st.expander("📋 Ver tabela de dados completa"):
                    colunas_tabela = [c for c in [
                        "ptd_id", "zona", "total_paineis_reais", "potencia_real_kwp", "producao_real_mwh_ano",
                        "custo_instalacao_eur", "val_eur", "tir_pct", "payback_anos", "racio_autossuficiencia",
                        "viavel",
                    ] if c in gdf_camara_ptds.columns]
                    st.dataframe(
                        gdf_camara_ptds[colunas_tabela].sort_values("total_paineis_reais", ascending=False),
                        use_container_width=True, hide_index=True,
                    )

                with st.expander("🏛️ Lista de edifícios da câmara carregados"):
                    st.dataframe(df_camara, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 4 — MAPA RÁCIO PRODUÇÃO / CONSUMO (CER)
# ═══════════════════════════════════════════════════════════════════
elif pagina == "⚖️ Mapa — Rácio Produção/Consumo (CER)":

    st.markdown('<p class="page-title">Mapa Interativo — Rácio Produção/Consumo</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-sub">Relação entre a produção fotovoltaica estimada e o consumo elétrico '
        'anual de cada PTD — indicador-chave de viabilidade para Comunidades de Energia Renovável</p>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Rácio = Produção anual (kWh) ÷ Consumo anual (kWh). Rácio ≥ 1 significa que a produção "
        "fotovoltaica estimada cobre (ou excede) o consumo total do PTD — cenário favorável para "
        "uma CER autossuficiente. Rácio < 1 indica produção insuficiente face ao consumo."
    )

    with st.expander("⚠️ Sobre o limite de potência do transformador (PTD)"):
        st.markdown("""
Este dashboard **não valida nem aplica nenhum limite de potência nominal do transformador**
de cada PTD (kVA de capacidade da rede). A coluna `potencia_real_kwp` apresentada é a
**potência fotovoltaica instalada resultante** do número de painéis calculado — não foi
verificado se essa potência é compatível com a capacidade de receção do respetivo PTD.

O número de painéis instaláveis (`total_paineis_reais`) é, segundo a documentação do
pipeline, limitado apenas pela **área de telhado disponível** (com fator de empacotamento
de 0,85), e não por nenhum limite de potência do posto de transformação.

Se a capacidade do transformador for relevante para a viabilidade real da CER, recomenda-se
confirmar essa lógica no notebook de cálculo de origem (fora do âmbito deste dashboard) e,
se necessário, adicionar uma coluna de capacidade nominal por PTD ao
**analise_economica_ptd.csv** para que possa ser validada e visualizada aqui.
""")

    if not dados_ok:
        st.error(f"Faltam ficheiros: **{VORONOI_GPKG}** e/ou **{ECONOMIA_CSV}**.")
    else:
        gdf_racio = gdf_mapa_4326[gdf_mapa_4326["racio_producao_consumo"].notna()].copy()

        if len(gdf_racio) == 0:
            st.warning(
                "Não há PTDs com dados de consumo (`consumo_anual_kwh`) válidos para calcular o "
                "rácio produção/consumo. Verifica o ficheiro **analise_economica_ptd.csv**."
            )
        else:
            # ── Filtros ──
            with st.expander("🔍 Filtros", expanded=False):
                zonas_sel_cer = filtro_zona(gdf_racio, key="cer_zona")
                fc1, fc2 = st.columns(2)
                with fc1:
                    racio_max_dados = float(gdf_racio["racio_producao_consumo"].max())
                    min_racio = st.slider(
                        "Rácio mínimo (Produção/Consumo)", 0.0,
                        round(racio_max_dados, 2) if racio_max_dados > 0 else 1.0, 0.0,
                    )
                with fc2:
                    so_autossuficientes = st.checkbox(
                        "Mostrar apenas PTDs autossuficientes (rácio ≥ 1)", value=False
                    )

            gdf_racio_filtrado = aplicar_filtro_zona(gdf_racio, zonas_sel_cer)
            gdf_racio_filtrado = gdf_racio_filtrado[gdf_racio_filtrado["racio_producao_consumo"] >= min_racio].copy()
            if so_autossuficientes:
                gdf_racio_filtrado = gdf_racio_filtrado[gdf_racio_filtrado["racio_producao_consumo"] >= 1]

            if len(gdf_racio_filtrado) == 0:
                st.info("Nenhum PTD cumpre os filtros selecionados.")
            else:
                # ── KPIs ──
                k1, k2, k3 = st.columns(3)
                with k1:
                    st.markdown(
                        f'<div class="metric-card"><div class="label">PTDs no filtro</div>'
                        f'<div class="big">{fmt_num(gdf_racio_filtrado["ptd_id"].nunique())}</div></div>',
                        unsafe_allow_html=True,
                    )
                with k2:
                    producao_total = gdf_racio_filtrado["producao_real_mwh_ano"].sum()
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Produção Total</div>'
                        f'<div class="big">{producao_total:,.0f} MWh</div></div>',
                        unsafe_allow_html=True,
                    )
                with k3:
                    consumo_total = gdf_racio_filtrado["consumo_anual_kwh"].sum() / 1000
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Consumo Total</div>'
                        f'<div class="big">{consumo_total:,.0f} MWh</div></div>',
                        unsafe_allow_html=True,
                    )

                k4, k5, k6 = st.columns(3)
                with k4:
                    racio_medio = gdf_racio_filtrado["racio_producao_consumo"].mean()
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Rácio Médio</div>'
                        f'<div class="big">{racio_medio:.2f}</div></div>',
                        unsafe_allow_html=True,
                    )
                with k5:
                    n_autossuf = (gdf_racio_filtrado["racio_producao_consumo"] >= 1).sum()
                    st.markdown(
                        f'<div class="metric-card"><div class="label">PTDs Autossuficientes</div>'
                        f'<div class="big">{fmt_num(n_autossuf)}</div></div>',
                        unsafe_allow_html=True,
                    )
                with k6:
                    racio_max = gdf_racio_filtrado["racio_producao_consumo"].max()
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Rácio Máximo</div>'
                        f'<div class="big">{racio_max:.2f}</div></div>',
                        unsafe_allow_html=True,
                    )

                k7, k8, k9 = st.columns(3)
                with k7:
                    autoconsumo_total = gdf_racio_filtrado["autoconsumo_kwh"].sum() / 1000
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Autoconsumo (ano 1)</div>'
                        f'<div class="big">{autoconsumo_total:,.0f} MWh</div></div>',
                        unsafe_allow_html=True,
                    )
                with k8:
                    excedente_total = gdf_racio_filtrado["excedente_kwh"].sum() / 1000
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Excedente p/ Rede (ano 1)</div>'
                        f'<div class="big">{excedente_total:,.0f} MWh</div></div>',
                        unsafe_allow_html=True,
                    )
                with k9:
                    poupanca_total = gdf_racio_filtrado["poupanca_ano1_eur"].sum()
                    st.markdown(
                        f'<div class="metric-card"><div class="label">Poupança Total (ano 1)</div>'
                        f'<div class="big">{fmt_eur(poupanca_total)}</div></div>',
                        unsafe_allow_html=True,
                    )
                st.caption(
                    "Autoconsumo = energia produzida usada localmente (valorizada a 0,25 €/kWh). "
                    "Excedente = produção acima do consumo, injetada na rede (tarifa RESP, 0,05 €/kWh)."
                )

                st.markdown('<div class="section-title">Mapa dos PTDs — Rácio Produção/Consumo</div>', unsafe_allow_html=True)
                st.caption(
                    "🟢 Tom mais escuro = rácio mais elevado (maior autossuficiência energética). "
                    "🟠 Laranja = rácio abaixo de 1 (produção insuficiente)."
                )

                centro = [
                    gdf_racio_filtrado.geometry.centroid.y.mean(),
                    gdf_racio_filtrado.geometry.centroid.x.mean(),
                ]
                m3 = folium.Map(location=centro, zoom_start=13, tiles="CartoDB positron")

                racio_max_mapa = gdf_racio_filtrado["racio_producao_consumo"].max() or 1

                def cor_por_racio(row):
                    r = row["racio_producao_consumo"]
                    if r >= 1:
                        frac = min(r / racio_max_mapa, 1.0) if racio_max_mapa else 0
                        return "#0B3D2E" if frac > 0.5 else "#1E7A52"
                    else:
                        return "#D98C3D" if r >= 0.5 else "#F2C18D"

                for _, row in gdf_racio_filtrado.iterrows():
                    racio_txt = f"{row['racio_producao_consumo']:.2f}"
                    autossuf_txt = "✅ Autossuficiente (≥1)" if row["racio_producao_consumo"] >= 1 else "⚠️ Produção insuficiente (<1)"
                    popup_html = f"""
                    <b>{row['rotulo']}</b><br>
                    <span style="font-size:11px;">{autossuf_txt}</span><br><br>
                    Rácio Produção/Consumo: <b>{racio_txt}</b><br>
                    Produção anual: <b>{row['producao_real_mwh_ano']:.1f} MWh</b><br>
                    Consumo anual: <b>{row['consumo_anual_kwh']:,.0f} kWh</b><br>
                    Autoconsumo: {row['autoconsumo_kwh']:,.0f} kWh &nbsp;|&nbsp; Excedente: {row['excedente_kwh']:,.0f} kWh<br>
                    Poupança ano 1: <b>{fmt_eur(row['poupanca_ano1_eur'])}</b><br>
                    Painéis instaláveis: {int(row['total_paineis_reais']):,}
                    """
                    folium.GeoJson(
                        row.geometry.__geo_interface__,
                        style_function=lambda feat, color=cor_por_racio(row): {
                            "fillColor": color, "color": "#3A3A3A", "weight": 0.6, "fillOpacity": 0.78,
                        },
                        tooltip=f"{row['rotulo']} · rácio {racio_txt}",
                        popup=folium.Popup(popup_html, max_width=290),
                    ).add_to(m3)

                adicionar_legenda(m3, "Legenda — Rácio Produção/Consumo", [
                    ("#0B3D2E", "Rácio ≥ 1 · elevado"),
                    ("#1E7A52", "Rácio ≥ 1 · moderado"),
                    ("#D98C3D", "Rácio 0,5 – 1"),
                    ("#F2C18D", "Rácio < 0,5"),
                ])

                st_folium(m3, width=None, height=560, returned_objects=[])

                # ── Gráfico Top 10 — maior rácio sempre no topo ──
                st.markdown('<div class="section-title">Top 10 PTDs — Maior Rácio Produção/Consumo</div>', unsafe_allow_html=True)
                top10_racio = gdf_racio_filtrado.nlargest(10, "racio_producao_consumo") \
                    .sort_values("racio_producao_consumo", ascending=False)
                fig6 = px.bar(
                    top10_racio, x="racio_producao_consumo", y="rotulo", orientation="h",
                    title="Top 10 — Rácio Produção/Consumo",
                    labels={"racio_producao_consumo": "Rácio (Produção ÷ Consumo)", "rotulo": ""},
                    color="racio_producao_consumo", color_continuous_scale="Greens",
                    text=top10_racio["racio_producao_consumo"].round(2),
                    category_orders={"rotulo": top10_racio["rotulo"].tolist()},
                )
                fig6.update_traces(textposition="outside", cliponaxis=False)
                fig6.add_vline(x=1, line_dash="dash", line_color="#A65300", annotation_text="Autossuficiência (rácio=1)")
                fig6.update_layout(
                    height=440, coloraxis_showscale=False, margin=dict(l=10, r=10, t=50, b=10),
                    yaxis=dict(tickfont=dict(size=11)),
                )
                st.plotly_chart(fig6, use_container_width=True)

                with st.expander("📋 Ver tabela de dados completa"):
                    colunas_tabela = [c for c in [
                        "ptd_id", "zona", "racio_producao_consumo", "producao_real_mwh_ano",
                        "consumo_anual_kwh", "autoconsumo_kwh", "excedente_kwh", "poupanca_ano1_eur",
                        "total_paineis_reais", "potencia_real_kwp",
                        "val_eur", "payback_anos", "viavel",
                    ] if c in gdf_racio_filtrado.columns]
                    st.dataframe(
                        gdf_racio_filtrado[colunas_tabela].sort_values("racio_producao_consumo", ascending=False),
                        use_container_width=True, hide_index=True,
                    )
