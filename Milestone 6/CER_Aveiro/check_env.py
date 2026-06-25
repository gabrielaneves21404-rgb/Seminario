"""
Verifica se todas as dependências estão instaladas e se os dados de entrada existem.
Executar antes de correr os notebooks: python check_env.py
"""
import sys
import importlib

REQUIRED_PACKAGES = [
    "geopandas", "pandas", "numpy", "matplotlib",
    "libpysal", "esda", "spreg", "pulp", "osmnx",
]

REQUIRED_DATA = [
    "data/raw/edificios_aveiro.gpkg",
    "data/raw/pvgis_aveiro.csv",
    "data/raw/serie_consumo_cp7_2024_2025_v2.csv",
    "data/raw/VoronoiPTD_Areas_Servico_Rede.gpkg",
]

print("=== Verificação de Ambiente ===\n")

# Packages
all_ok = True
for pkg in REQUIRED_PACKAGES:
    try:
        m = importlib.import_module(pkg)
        version = getattr(m, "__version__", "?")
        print(f"  ✓ {pkg} ({version})")
    except ImportError:
        print(f"  ✗ {pkg} — NÃO INSTALADO")
        all_ok = False

print()

# Data files
from pathlib import Path
for f in REQUIRED_DATA:
    p = Path(f)
    if p.exists():
        size_mb = p.stat().st_size / 1e6
        print(f"  ✓ {f} ({size_mb:.1f} MB)")
    else:
        print(f"  ✗ {f} — FICHEIRO EM FALTA")
        all_ok = False

print()
if all_ok:
    print("✅ Ambiente pronto. Pode correr os notebooks pela ordem: 04 → 01 → 02 → 03")
else:
    print("❌ Há dependências ou dados em falta. Consulte o README.md.")
    sys.exit(1)
