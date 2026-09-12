"""
Pobiera aktualną liczbę osób na basenie krytym MOSiR Łańcut ze strony:
https://mosir-lancut.pl/asp/pl_start.asp?typ=14&menu=135&strona=1

i dopisuje wynik do pliku data/basen_dane.csv.

Skrypt jest pomyślany do uruchamiania cyklicznie (np. co 15 minut) przez
GitHub Actions przez całą dobę — sam sprawdza, czy aktualna godzina (czasu
polskiego) mieści się w oknie 6:00–22:00, i poza tym oknem nic nie zapisuje.
"""

import csv
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

URL = "https://mosir-lancut.pl/asp/pl_start.asp?typ=14&menu=135&strona=1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "basen_dane.csv")
WARSAW = ZoneInfo("Europe/Warsaw")

GODZINA_START = 6   # 6:00
GODZINA_KONIEC = 22  # do 22:00 (wyłącznie)


def pobierz_dane():
    """Pobiera stronę i wyciąga parę liczb 'aktualnie/maksimum'."""
    resp = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    html = resp.text

    # Usuwamy znaczniki HTML i normalizujemy białe znaki, żeby regex
    # nie musiał znać dokładnej struktury tagów (ta może się zmieniać).
    tekst = re.sub(r"<[^>]+>", " ", html)
    tekst = re.sub(r"\s+", " ", tekst)

    m = re.search(
        r"OS[ÓO]B\s+NA\s+BASENIE\s*(\d{1,4})\s*/\s*(\d{1,4})",
        tekst,
        re.IGNORECASE,
    )
    if not m:
        raise RuntimeError(
            "Nie znaleziono licznika 'OSÓB NA BASENIE' na stronie — "
            "układ strony mógł się zmienić, trzeba poprawić regex."
        )

    aktualnie = int(m.group(1))
    maksimum = int(m.group(2))
    return aktualnie, maksimum


def w_oknie_godzinowym(teraz):
    return GODZINA_START <= teraz.hour < GODZINA_KONIEC


def zapisz(aktualnie, maksimum, teraz):
    nowy_plik = not os.path.exists(DATA_FILE)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if nowy_plik:
            writer.writerow(
                ["timestamp_pl", "data", "godzina", "minuta", "osoby", "maksimum"]
            )
        writer.writerow(
            [
                teraz.strftime("%Y-%m-%d %H:%M:%S"),
                teraz.strftime("%Y-%m-%d"),
                teraz.hour,
                teraz.minute,
                aktualnie,
                maksimum,
            ]
        )


def main():
    teraz = datetime.now(WARSAW)

    if not w_oknie_godzinowym(teraz):
        print(f"Poza oknem {GODZINA_START}:00–{GODZINA_KONIEC}:00 "
              f"({teraz.strftime('%Y-%m-%d %H:%M')} czasu PL) — pomijam zapis.")
        return

    try:
        aktualnie, maksimum = pobierz_dane()
    except Exception as e:
        print(f"Błąd pobierania danych: {e}", file=sys.stderr)
        sys.exit(1)

    zapisz(aktualnie, maksimum, teraz)
    print(
        f"{teraz.strftime('%Y-%m-%d %H:%M')} czasu PL -> "
        f"{aktualnie}/{maksimum} osób na basenie (zapisano do {DATA_FILE})"
    )


if __name__ == "__main__":
    main()
