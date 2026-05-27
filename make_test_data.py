from pathlib import Path
import pandas as pd

DATA_DIR = Path("data_test")
DATA_DIR.mkdir(exist_ok=True)

# 1. Débit entrant, au pas de temps 15 min
debit = pd.DataFrame({
    "date": pd.date_range("2022-01-01 00:00", periods=8, freq="15min"),
    "input flowrate (m3/s)": [30, 40, 45, 50, 30, 30, 30, 30],
})

debit.to_csv(DATA_DIR / "debit_SAV_2022.csv", index=False)

# 2. Concentration entrée journalière
# Valeur volontairement simple : 100 mgN/L
conc_entree = pd.DataFrame({
    "date": [pd.Timestamp("2022-01-01")],
    "concentration NGL (mgN/L)": [100],
})

conc_entree.to_csv(DATA_DIR / "concentration_entree_SAV.csv", index=False)

# 3. Courbe sortie estivale
# Ici elle ne sera pas utilisée car on est en janvier, mais on la crée quand même.
conc_sortie_ete = pd.DataFrame({
    "debit (m3/j)": [0, 2_592_000, 3_628_800, 4_320_000],  # 0, 30, 42, 50 m3/s
    "concentration NGL (mgN/L)": [5, 5, 5, 5],
})

conc_sortie_ete.to_csv(DATA_DIR / "concentration_sortie_SAV_estivale.csv", index=False)

# 4. Courbe sortie hivernale
# Concentration constante pour faciliter les calculs : 10 mgN/L
conc_sortie_hiver = pd.DataFrame({
    "debit (m3/j)": [0, 2_592_000, 3_628_800, 4_320_000],  # 0, 30, 42, 50 m3/s
    "concentration NGL (mgN/L)": [10, 10, 10, 10],
})

conc_sortie_hiver.to_csv(DATA_DIR / "concentration_sortie_SAV_hivernale.csv", index=False)

print("Données test créées dans data_test/")
