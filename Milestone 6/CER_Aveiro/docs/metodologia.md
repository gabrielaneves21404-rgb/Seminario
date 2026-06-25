# Notas Metodológicas — Aveiro CER Solar

## 1. Fonte de Dados Solares (PVGIS)

Os dados de irradiação são obtidos gratuitamente no portal **PVGIS (Photovoltaic Geographical Information System)** do JRC — Comissão Europeia:

- URL: https://re.jrc.ec.europa.eu/pvg_tools/
- Ferramenta: **Hourly radiation**
- Localização: centro do município de Aveiro (~40.64°N, -8.65°W)
- Série: múltiplos anos (o script lida com qualquer número de anos)
- Coluna usada: `G(i)` — irradiação global no plano inclinado (W/m²)

### Como obter o ficheiro `pvgis_aveiro.csv`

1. Aceder a https://re.jrc.ec.europa.eu/pvg_tools/
2. Selecionar "Hourly radiation"
3. Definir coordenadas: Lat=40.6413, Lon=-8.6536
4. Selecionar período multi-anual disponível
5. Exportar como CSV
6. Guardar em `data/raw/pvgis_aveiro.csv`

---

## 2. Dados de Edifícios (`edificios_aveiro.gpkg`)

O GeoPackage contém as pegadas dos edifícios do município de Aveiro com o CP7 atribuído por sobreposição espacial. A layer usada é `postal_code_buildings_assigned`.

### Colunas principais

| Coluna | Descrição |
|--------|-----------|
| `cp7` | Código postal de 7 dígitos |
| `polygon_id` | Identificador único do edifício |
| `building_postal_fragment_area_m2` | Área do edifício atribuída a este CP7 |
| `building_area_m2` | Área total do edifício |
| `n_cp7_on_building` | Número de CP7s que partilham o edifício |

### Nota sobre edifícios partilhados

Edifícios na fronteira de dois CP7s têm `n_cp7_on_building > 1`. A área é dividida proporcionalmente (`building_postal_fragment_area_m2`), garantindo que a soma dos fragmentos iguala a área total.

---

## 3. Parâmetros Fotovoltaicos

| Parâmetro | Valor | Justificação |
|-----------|-------|-------------|
| `ETA_PAINEL` | 0.20 | Eficiência típica de módulos mono-Si de mercado (2024) |
| `PR` | 0.80 | Performance Ratio: perdas térmicas, cabos, inversor (~20%) |
| `FATOR_OCUPACAO` | 0.40 | 40% da área total do telhado é tecnicamente utilizável (declive, chaminés, claraboias) |
| `FATOR_EMPACOTAMENTO` | 0.85 | 15% adicional perdido por margens de recuo e corredores de manutenção |

**Fórmula de produção:**
```
Produção (kWh/ano) = H_anual × Area_util × ETA × PR
```

Onde `Area_util = Area_fragmento × FATOR_OCUPACAO`.

---

## 4. Voronoi de Rede (PTDs)

A delimitação das áreas de serviço de cada PTD foi calculada usando **distâncias de trajeto via rede de ruas** (OSMnx), não distâncias euclidianas. Este método é mais realista porque a energia elétrica percorre a infraestrutura física existente.

### Cobertura espacial

A tesselação de Voronoi de rede não cobre o território de forma perfeitamente contígua — existem margens de alguns metros entre áreas adjacentes. A estratégia adotada foi:

1. **Match direto** (`predicate="within"`): centroide do edifício estritamente dentro do polígono
2. **Match por proximidade** (`sjoin_nearest`, limite ≤ 1000 m): para os restantes

Apenas 3 edifícios (CP7s 3800-901/902/903) ficaram a >1 km de qualquer PTD e foram excluídos.

---

## 5. Dados de Consumo (E-Redes)

O ficheiro `serie_consumo_cp7_2024_2025_v2.csv` contém leituras horárias de energia ativa por CP7, fornecidas pela E-Redes. **Estes dados são confidenciais e não podem ser redistribuídos.**

### Filtros aplicados

- **Mínimo de 70 registos horários** por CP7 (integridade mínima)
- **Consumo máximo de 5 GWh/ano** por CP7 (exclusão de grandes consumidores industriais)

### Extrapolação anual

```python
consumo_anual = (consumo_acumulado / n_registos) * 8760
```

---

## 6. Reprodução com Dados Sintéticos

Para reproduzir a pipeline sem acesso aos dados reais da E-Redes, é possível gerar um dataset sintético com a estrutura correta:

```python
import pandas as pd
import numpy as np

np.random.seed(42)
n_cp7 = 700

df_synthetic = pd.DataFrame({
    "cp7": [f"3800-{str(i).zfill(3)}" for i in range(1, n_cp7+1)],
    "energia_ativa_kwh": np.random.exponential(scale=50, size=n_cp7 * 100),
    # Simular ~100 registos por CP7
})
# Repetir cada CP7 ~100 vezes
df_synthetic = df_synthetic.sample(frac=1).reset_index(drop=True)
df_synthetic.to_csv("data/raw/serie_consumo_cp7_2024_2025_v2.csv", index=False)
```

> **Atenção:** Os resultados com dados sintéticos não têm validade científica — servem apenas para testar a pipeline técnica.

---

## 7. Econometria Espacial

### Escolha da Matriz W

A contiguidade **Queen** inicial gerou 217 ilhas (CP7s sem vizinhos), causando problemas numéricos. A solução foi substituir por **KNN com k=4**, que garante exatamente 4 vizinhos para cada CP7.

### Interpretação do I de Moran

- **I = 0.1703, p < 0.001** → autocorrelação espacial positiva e significativa
- Zonas com alta produção solar tendem a estar próximas de outras zonas com alta produção (efeito de clustering)

### Escolha SAR vs SEM

- **SAR (Spatial Lag):** modela o efeito de spillover — a taxa de autossuficiência de um CP7 é influenciada pela dos vizinhos
- **SEM (Spatial Error):** modela autocorrelação nos resíduos
- **Critério:** AIC SAR (6494.9) < AIC SEM (6502.0) → SAR é o modelo preferido

---

## 8. Optimização MILP

O problema de selecção de CP7s a financiar é formulado como MILP binário:

**Variáveis:** $x_i \in \{0,1\}$ (investir ou não em cada CP7 deficitário)

**Objetivo:** maximizar o número de CP7s que atingem autossuficiência

**Restrição:** orçamento total ≤ 5 M€

**Solver:** PuLP + CBC (open-source, sem licença necessária)

### Limitações do modelo

- Não inclui custos de O&M (~1%/ano do investimento)
- Não modela restrições de capacidade da rede (potência máxima por PTD)
- Assume instalação total do défice em ano zero
- CP7s com área insuficiente para eliminar o défice são excluídos (investimento parcial não conta para a métrica de autossuficiência)
