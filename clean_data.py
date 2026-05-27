from pathlib import Path

import pandas as pd


RAW_DIR = Path("data_raw")
CLEAN_DIR = Path("data_clean")
CLEAN_DIR.mkdir(exist_ok=True)

FLOW_COL = "input flowrate (m3/s)"
CONC_COL = "concentration NGL (mgN/L)"


def clean_debit():
    df = pd.read_csv(RAW_DIR / "Debit_SAV_2022.csv", sep=";", decimal=",")
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df[FLOW_COL] = df[FLOW_COL].interpolate().ffill().bfill()
    df.to_csv(CLEAN_DIR / "Debit_SAV_2022.csv", index=False)


def clean_inlet_concentration():
    df = pd.read_csv(RAW_DIR / "concentration_entree_SAV.csv", sep=";", decimal=",")
    df = df.dropna(how="all")
    df["date"] = pd.to_datetime(df["date"], dayfirst=True).dt.normalize()
    df.to_csv(CLEAN_DIR / "concentration_entree_SAV.csv", index=False)


def clean_winter_outlet_concentration():
    df = pd.read_csv(RAW_DIR / "concentration_sortie_SAV_hivernale.csv", sep=";", decimal=",")
    df.loc[0, CONC_COL] = 14
    df.to_csv(CLEAN_DIR / "concentration_sortie_SAV_hivernale.csv", index=False)


def copy_summer_outlet_concentration():
    df = pd.read_csv(RAW_DIR / "concentration_sortie_SAV_estivale.csv", sep=";", decimal=",")
    df.to_csv(CLEAN_DIR / "concentration_sortie_SAV_estivale.csv", index=False)


def main():
    clean_debit()
    clean_inlet_concentration()
    clean_winter_outlet_concentration()
    copy_summer_outlet_concentration()
    print("Nettoyage terminé. Fichiers écrits dans data_clean/")


if __name__ == "__main__":
    main()
