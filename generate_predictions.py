"""
Generuje predictions.json — gotową tabelę predykcji (godzina x dzień
tygodnia x miesiąc) na podstawie wytrenowanego model_frekwencji.pkl.

Dzięki temu dashboard (index.html) może pokazywać przewidywaną frekwencję
bez uruchamiania Pythona w przeglądarce — po prostu odczytuje wartość
z gotowej tabeli.

Uwaga o kodowaniu dnia tygodnia: używamy konwencji pandas/Python
(poniedziałek=0 ... niedziela=6), bo tak trenował się model. Dashboard
w JS konwertuje JS Date.getDay() (niedziela=0) na tę konwencję.

Uruchom po każdym treningu modelu: python generate_predictions.py
"""

import json
import os

import joblib
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(SCRIPT_DIR, "model_frekwencji.pkl")
OUT_FILE = os.path.join(SCRIPT_DIR, "data", "predictions.json")

GODZINY = list(range(6, 22))
DNI_TYGODNIA = list(range(7))  # 0=poniedziałek..6=niedziela
MIESIACE = list(range(1, 13))


def main():
    zaladowane = joblib.load(MODEL_FILE)
    model = zaladowane["model"]
    cechy = zaladowane["cechy"]

    wiersze = []
    for miesiac in MIESIACE:
        for dzien in DNI_TYGODNIA:
            for godzina in GODZINY:
                wiersze.append({
                    "godzina": godzina,
                    "dzien_tygodnia": dzien,
                    "miesiac": miesiac,
                    "is_weekend": 1 if dzien in (5, 6) else 0,
                    "temperatura": np.nan,
                    "kod_pogody": np.nan,
                })

    X = pd.DataFrame(wiersze)[cechy]
    predykcje = model.predict(X)

    tabela = {}
    for wiersz, wartosc in zip(wiersze, predykcje):
        m = str(wiersz["miesiac"])
        d = str(wiersz["dzien_tygodnia"])
        g = str(wiersz["godzina"])
        tabela.setdefault(m, {}).setdefault(d, {})[g] = round(float(wartosc), 1)

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tabela, f, ensure_ascii=False, indent=1)

    print(f"Zapisano tabelę predykcji: {OUT_FILE}")


if __name__ == "__main__":
    main()
