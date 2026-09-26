"""
Trenuje model przewidujący liczbę osób na basenie na podstawie:
- godziny, dnia tygodnia, miesiąca, czy to weekend,
- temperatury i kodu pogodowego (jeśli dostępne — brakujące wartości
  są tolerowane, HistGradientBoostingRegressor radzi sobie z NaN natywnie,
  więc starsze wiersze bez pogody nie są odrzucane, tylko mniej informacyjne).

Zapisuje:
- model_frekwencji.pkl — wytrenowany model (joblib)
- model_info.json — data treningu, błąd (MAE) na zbiorze testowym, użyte cechy

Uruchom lokalnie: python train_model.py
Albo ręcznie z zakładki Actions na GitHubie (workflow "Trenowanie modelu frekwencji").
"""

import json
import os
import re
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "basen_dane.csv")
MODEL_FILE = os.path.join(SCRIPT_DIR, "model_frekwencji.pkl")
INFO_FILE = os.path.join(SCRIPT_DIR, "model_info.json")

CECHY = ["godzina", "dzien_tygodnia", "miesiac", "is_weekend", "temperatura", "kod_pogody"]


def _kod_pogody(w):
    """Wyciąga numeryczny kod z tekstu w stylu '61 - Deszcz lekki' -> 61.0"""
    if not isinstance(w, str) or not w.strip():
        return np.nan
    m = re.match(r"(\d+)", w.strip())
    return float(m.group(1)) if m else np.nan


def wczytaj_dane():
    df = pd.read_csv(DATA_FILE)
    df["data"] = pd.to_datetime(df["data"])
    df["dzien_tygodnia"] = df["data"].dt.dayofweek  # 0=poniedziałek..6=niedziela
    df["miesiac"] = df["data"].dt.month
    df["is_weekend"] = df["dzien_tygodnia"].isin([5, 6]).astype(int)

    if "warunki" in df.columns:
        df["kod_pogody"] = df["warunki"].apply(_kod_pogody)
    else:
        df["kod_pogody"] = np.nan

    if "temperatura" in df.columns:
        df["temperatura"] = pd.to_numeric(df["temperatura"], errors="coerce")
    else:
        df["temperatura"] = np.nan

    return df


def main():
    df = wczytaj_dane()

    if len(df) < 30:
        print(f"Za mało danych do sensownego treningu ({len(df)} wierszy) — pomijam.")
        return

    X = df[CECHY]
    y = df["osoby"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = HistGradientBoostingRegressor(random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)

    joblib.dump({"model": model, "cechy": CECHY}, MODEL_FILE)

    info = {
        "wytrenowano": datetime.now().isoformat(timespec="seconds"),
        "liczba_wierszy_ogolem": len(df),
        "liczba_wierszy_treningowych": len(X_train),
        "liczba_wierszy_testowych": len(X_test),
        "mae_osob": round(float(mae), 2),
        "cechy": CECHY,
    }
    with open(INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"Model wytrenowany na {len(df)} wierszach.")
    print(f"Średni błąd (MAE) na zbiorze testowym: {mae:.2f} osoby.")
    print(f"Zapisano: {MODEL_FILE} oraz {INFO_FILE}")


if __name__ == "__main__":
    main()
