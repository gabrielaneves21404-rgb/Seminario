import streamlit as st
import pandas as pd

# Configuração da página do Streamlit
st.set_page_config(page_title="Análise CER - Áreas Mistas", layout="wide")

st.title("📊 Análise de Viabilidade Económica - Comunidade de Energia")
st.markdown("Selecione uma área mista para analisar os indicadores financeiros individuais baseados no perfil Dia (Industrial) e Noite (Permanente).")

# 1. Carregar os dados calculados no passo anterior
@st.cache_data
def carregar_dados():
    return pd.read_csv("dados_areas_financeiro.csv")

df = carregar_dados()

# 2. Criar a estrutura de ecrã (Painel Lateral + Área Principal)
st.sidebar.header("🔍 Seleção de Área")
area_selecionada = st.sidebar.selectbox(
    "Escolha a Área Mista:",
    options=df['ID_Area'].unique()
)

# Filtrar o DataFrame para a área que o utilizador escolheu
dados_area = df[df['ID_Area'] == area_selecionada].iloc[0]

# 3. Mostrar os Indicadores Financeiros em Destaque na Barra Lateral (Sidebar)
st.sidebar.markdown("---")
st.sidebar.subheader("💰 Indicadores Económicos")

# Formatação visual usando st.sidebar.metric
st.sidebar.metric(
    label="Investimento Inicial (CAPEX)", 
    value=f"{dados_area['CAPEX']:,.2f} €"
)

st.sidebar.metric(
    label="VAL (Valor Atual Líquido)", 
    value=f"{dados_area['VAL']:,.2f} €",
    delta=f"+ Poupança Real" if dados_area['VAL'] > 0 else "- Prejuízo"
)

st.sidebar.metric(
    label="TIR (Taxa Interna Rentabilidade)", 
    value=f"{dados_area['TIR_%']:.2f} %"
)

# Validação caso o payback seja nulo/não se pague
payback_val = dados_area['Payback_Anos']
payback_texto = f"{int(payback_val)} anos" if not pd.isna(payback_val) else "Não se paga em 25 anos"
st.sidebar.metric(
    label="Payback Descontado", 
    value=payback_texto
)

# 4. Conteúdo Principal da Página (Gráficos e Detalhes Técnicos)
col1, col2 = st.columns(2)

with col1:
    st.subheader(f"📈 Perfil Energético da {area_selecionada}")
    # Criar um pequeno sumário dos dados técnicos daquela área
    st.write(f"**Número de Painéis Planeados:** {int(dados_area['Paineis_Necessarios'])} unidades")
    st.write(f"**Consumo Diurno Estimado (Indústria):** {dados_area['Energia_Dia_kWh']:,.0f} kWh/ano")
    st.write(f"**Consumo Noturno Estimado (Permanente):** {dados_area['Energia_Noite_kWh']:,.0f} kWh/ano")

with col2:
    st.subheader("💡 Conclusão de Viabilidade")
    if dados_area['VAL'] > 0:
        st.success(f"A **{area_selecionada}** é altamente viável! O projeto apresenta um retorno sólido com uma taxa de rentabilidade de {dados_area['TIR_%']:.2f}%, amortizando o investimento em {payback_texto}.")
    else:
        st.error(f"A **{area_selecionada}** não apresenta viabilidade financeira atrativa sob as atuais taxas de desconto.")

# Mostrar a tabela de dados brutos caso queiram auditar
st.markdown("---")
st.subheader("📋 Tabela Comparativa de todas as Áreas Viáveis")
st.dataframe(df)