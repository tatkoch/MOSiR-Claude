"""
Sprawdza predykcję wytrenowanego modelu dla podanych warunków.

Przykład:
    python predict.py --godzina 14 --dzien sobota --miesiac 7 --temperatura 25 --kod-pogody 1

Jeśli nie podasz temperatury/kodu pogody, model i tak zwróci predykcję
(HistGradientBoostingRegressor toleruje brakujące wartości).
"""

import argparse

import joblib

DNI = {
    "poniedzialek": 0, "wtorek": 1, "sroda": 2, "czwartek": 3,
    "piatek": 4, "sobota": 5, "niedziela": 6,
}


def main():
    parser = argparse.ArgumentParser(description="Predykcja obłożenia basenu")
    parser.add_argument("--godzina", type=int, required=True, help="6-21")
    parser.add_argument("--dzien", choices=DNI.keys(), required=True)
    parser.add_argument("--miesiac", type=int, required=True, help="1-12")
    parser.add_argument("--temperatura", type=float, default=None)
    parser.add_argument("--kod-pogody", type=float, default=None, dest="kod_pogody")
    args = parser.parse_args()

    zaladowane = joblib.load("model_frekwencji.pkl")
    model = zaladowane["model"]
    cechy = zaladowane["cechy"]

    dzien_tygodnia = DNI[args.dzien]
    is_weekend = 1 if dzien_tygodnia in (5, 6) else 0

    wiersz = {
        "godzina": args.godzina,
        "dzien_tygodnia": dzien_tygodnia,
        "miesiac": args.miesiac,
        "is_weekend": is_weekend,
        "temperatura": args.temperatura,
        "kod_pogody": args.kod_pogody,
    }

    import pandas as pd
    X = pd.DataFrame([wiersz])[cechy]
    predykcja = model.predict(X)[0]

    print(f"Przewidywana liczba osób: {predykcja:.0f}")


if __name__ == "__main__":
    main()
