from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DATA_DIR = Path("data_clean")
OUTPUT_DIR = Path("outputs_simple")
OUTPUT_DIR.mkdir(exist_ok=True)

CAPACITY_M3S = 41.5
BASIN_VOLUME_M3 = 500_000.0
DT_S = 15 * 60
FILL_THRESHOLD_M3S = 41.5
DRAIN_THRESHOLD_M3S = 20.0
DRAIN_FLOW_M3S = 2.0
#DRAIN_THRESHOLD_M3S = 20.0
#DRAIN_FLOW_M3S = 2.0

FLOW_COL = "input flowrate (m3/s)"
IN_CONC_COL = "concentration NGL (mgN/L)"
CURVE_FLOW_COL = "debit (m3/j)"
CURVE_CONC_COL = "concentration NGL (mgN/L)"


def is_summer(dates):
    month_day = dates.dt.month * 100 + dates.dt.day
    return (month_day >= 415) & (month_day <= 1015)


def load_inputs(data_dir):
    flow = pd.read_csv(data_dir / "debit_SAV_2022.csv", parse_dates=["date"])
    in_conc = pd.read_csv(data_dir / "concentration_entree_SAV.csv", parse_dates=["date"])
    summer_curve = pd.read_csv(data_dir / "concentration_sortie_SAV_estivale.csv")
    winter_curve = pd.read_csv(data_dir / "concentration_sortie_SAV_hivernale.csv")
    flow["is_summer"] = is_summer(flow["date"])
    return flow, in_conc, summer_curve, winter_curve


def interpolate_outlet_concentration(q_treated_m3s, summer_mask, summer_curve, winter_curve):
    q_treated_m3s = np.asarray(q_treated_m3s, dtype=float)
    out = np.empty_like(q_treated_m3s)

    for mask, curve in [(summer_mask, summer_curve), (~summer_mask, winter_curve)]:
        curve_flow_m3s = curve[CURVE_FLOW_COL].to_numpy() / 86400
        curve_conc = curve[CURVE_CONC_COL].to_numpy()
        out[mask] = np.interp(q_treated_m3s[mask], curve_flow_m3s, curve_conc)

    return out


def mass_kg(q_m3s, concentration_mg_l):
    return np.asarray(q_m3s) * DT_S * np.asarray(concentration_mg_l) / 1000


def add_inlet_concentration(flow, in_conc):
    conc_by_day = in_conc.set_index("date")[IN_CONC_COL]
    flow = flow.copy()
    flow["conc_entree_mg_l"] = flow["date"].dt.normalize().map(conc_by_day)
    return flow

def simulate_without_basin(ts, conc_entree, curve_summer, curve_winter):
    out = ts.copy()
    conc_par_jour = conc_entree.set_index("date")["concentration NGL (mgN/L)"]
    out["conc_entree_mg_l"] = out["date"].dt.normalize().map(conc_par_jour)

    q_in = out["input flowrate (m3/s)"].to_numpy()

    out["q_traite_m3s"] = np.minimum(q_in, CAPACITY_M3S)
    out["q_deverse_non_traite_m3s"] = np.maximum(q_in - CAPACITY_M3S, 0.0)

    conc_sortie = interpolate_outlet_concentration(out["q_traite_m3s"].to_numpy(), out["is_summer"].to_numpy(dtype=bool), curve_summer,curve_winter)

    out["conc_sortie_mg_l"] = conc_sortie

    out["masse_traitee_kg"] = mass_kg(out["q_traite_m3s"].to_numpy(), conc_sortie)

    out["masse_non_traitee_kg"] = mass_kg(out["q_deverse_non_traite_m3s"].to_numpy(), out["conc_entree_mg_l"].to_numpy())

    out["masse_totale_kg"] = out["masse_traitee_kg"] + out["masse_non_traitee_kg"]

    return out

def simulate_with_basin(flow, in_conc, summer_curve, winter_curve):
    out = add_inlet_concentration(flow, in_conc)
    q_in = out[FLOW_COL].to_numpy()
    n = len(out)

    q_treated = np.zeros(n)
    q_overflow = np.zeros(n)
    q_to_basin = np.zeros(n)
    q_drain = np.zeros(n)
    stock = np.zeros(n)

    current_stock = 0.0

    for i, q in enumerate(q_in):
        if q > FILL_THRESHOLD_M3S:
            surplus = q - FILL_THRESHOLD_M3S
            available_volume = max(BASIN_VOLUME_M3 - current_stock, 0.0)
            q_stored = min(surplus, available_volume / DT_S)

            q_to_basin[i] = q_stored
            q_overflow[i] = max(surplus - q_stored, 0.0)
            q_treated[i] = min(FILL_THRESHOLD_M3S, CAPACITY_M3S)
            current_stock += q_stored * DT_S

        elif q < DRAIN_THRESHOLD_M3S and current_stock > 0.0:
            available_capacity = max(CAPACITY_M3S - q, 0.0)
            q_drained = min(DRAIN_FLOW_M3S, current_stock / DT_S, available_capacity)

            q_drain[i] = q_drained
            q_treated[i] = q + q_drained
            current_stock -= q_drained * DT_S

        else:
            q_treated[i] = min(q, CAPACITY_M3S)
            q_overflow[i] = max(q - CAPACITY_M3S, 0.0)

        stock[i] = current_stock

    out["q_traite_m3s"] = q_treated
    out["q_deverse_non_traite_m3s"] = q_overflow
    out["q_vers_bassin_m3s"] = q_to_basin
    out["q_vidange_m3s"] = q_drain
    out["stock_bassin_m3"] = stock

    outlet_conc = interpolate_outlet_concentration(q_treated, out["is_summer"].to_numpy(dtype=bool), summer_curve,winter_curve)
    out["conc_sortie_mg_l"] = outlet_conc
    out["masse_traitee_kg"] = mass_kg(q_treated, outlet_conc)
    out["masse_non_traitee_kg"] = mass_kg(q_overflow, out["conc_entree_mg_l"].to_numpy())
    out["masse_totale_kg"] = out["masse_traitee_kg"] + out["masse_non_traitee_kg"]

    return out


def print_summary(result):
    total_mass_t = result["masse_totale_kg"].sum() / 1000
    untreated_mass_t = result["masse_non_traitee_kg"].sum() / 1000
    max_stock = result["stock_bassin_m3"].max()
    final_stock = result["stock_bassin_m3"].iloc[-1]

    print(f"Masse totale rejetée avec bassin : {total_mass_t:.2f} tN")
    print(f"Masse non traitée rejetée : {untreated_mass_t:.2f} tN")
    print(f"Stock maximal du bassin : {max_stock:,.0f} m³")
    print(f"Stock final du bassin : {final_stock:,.0f} m³")


def main():
    flow, in_conc, summer_curve, winter_curve = load_inputs(DATA_DIR)
    without_basin = simulate_without_basin(flow, in_conc, summer_curve, winter_curve)
    with_basin = simulate_with_basin(flow, in_conc, summer_curve, winter_curve)
    masse_sans_tn = without_basin["masse_totale_kg"].sum() / 1000
    masse_avec_tn = with_basin["masse_totale_kg"].sum() / 1000
    gain_tn = masse_sans_tn - masse_avec_tn
    print("\n=== CONFIGURATION TESTÉE ===")
    print("Seuil de vidange :", DRAIN_THRESHOLD_M3S, "m³/s")
    print("Débit de vidange :", DRAIN_FLOW_M3S, "m³/s")
    print("\n=== RÉSULTATS HYDRAULIQUES ===")
    print("Stock max m3 :", with_basin["stock_bassin_m3"].max())
    print("Stock final m3 :", with_basin["stock_bassin_m3"].iloc[-1])
    print("Nombre de pas de vidange :", (with_basin["q_vidange_m3s"] > 0).sum())
    print("Débit max de vidange observé :", with_basin["q_vidange_m3s"].max())
    print("\n=== GAIN ===")
    print(f"Masse sans bassin : {masse_sans_tn:.3f} tN")
    print(f"Masse avec bassin : {masse_avec_tn:.3f} tN")
    print(f"Gain : {gain_tn:.3f} tN")
    with_basin.to_csv(OUTPUT_DIR / "chronique_avec_bassin.csv", index=False)
    without_basin.to_csv(OUTPUT_DIR / "chronique_sans_bassin.csv", index=False)
    print_summary(with_basin)


if __name__ == "__main__":
    main()
