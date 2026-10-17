"""
Pobiera aktualną liczbę osób na basenie krytym MOSiR Łańcut ze strony:
https://mosir-lancut.pl/asp/pl_start.asp?typ=14&menu=135&strona=1
oraz bieżącą pogodę dla Łańcuta (Open-Meteo, bez klucza API),
i dopisuje wynik do pliku data/basen_dane.csv.

Skrypt jest wyzwalany z zewnątrz (przez harmonogram na NAS, przez curl
wywołujący workflow_dispatch) — sam sprawdza, czy aktualna godzina (czasu
polskiego) mieści się w oknie 6:00–22:00, i poza tym oknem nic nie zapisuje.
"""

import csv
import html
import os
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

URL = "https://mosir-lancut.pl/asp/pl_start.asp?typ=14&menu=135&strona=1"
POGODA_URL = "https://api.open-meteo.com/v1/forecast?latitude=50.068&longitude=22.231&current_weather=true"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "basen_dane.csv")
WARSAW = ZoneInfo("Europe/Warsaw")

GODZINA_START = 6   # 6:00
GODZINA_KONIEC = 22  # do 22:00 (wyłącznie)

KODY_POGODY = {
    0: "Bezchmurnie", 1: "Głównie słonecznie", 2: "Częściowo pochmurno",
    3: "Zachmurzenie całkowite", 45: "Mgła", 48: "Osadzająca się mgła",
    51: "Mżawka lekka", 53: "Mżawka umiarkowana", 55: "Mżawka gęsta",
    61: "Deszcz lekki", 63: "Deszcz umiarkowany", 65: "Deszcz intensywny",
    71: "Śnieg lekki", 73: "Śnieg umiarkowany", 75: "Śnieg intensywny",
    80: "Przelotne opady deszczu", 81: "Przelotne opady umiarkowane",
    82: "Przelotne opady intensywne", 95: "Burza", 96: "Burza z lekkim gradem",
    99: "Burza z silnym gradem",
}


class BasenZamkniety(Exception):
    """Basen jest w tej chwili zamknięty / nieczynny (np. dzień sanitarny) — brak liczby do zapisania."""
    pass


FRAZY_ZAMKNIECIA = [
    "DZIEŃ SANITARNY", "DZIEN SANITARNY", "PRZERWA TECHNICZNA",
    "PRZERWA KONSERWACYJNA", "NIECZYNNY", "NIECZYNNA", "NIECZYNNE",
    "BASEN ZAMKNIĘTY", "BASEN ZAMKNIETY", "ZAMKNIĘTY BASEN",
]


MAKS_OKNO_ZNAKOW = 200     # ile znaków za napisem „OSÓB NA BASENIE” przeszukujemy
MAKS_POJEMNOSC_MIN = 10    # sensowny zakres „maksimum” (limit osób na basenie)
MAKS_POJEMNOSC_MAX = 500


class LicznikNieczytelny(Exception):
    """Strona się pobrała, ale licznika nie da się odczytać (np. ktoś wpisał tam bzdury)."""
    pass


def wyciagnij_licznik(tekst):
    """Z oczyszczonego tekstu strony wyciąga parę (aktualnie, maksimum).

    Sprawdza KAŻDE wystąpienie napisu „OSÓB NA BASENIE” (może być też w menu
    czy tytule) i w każdym oknie szuka pary „X/Y”. Para musi przejść kontrolę
    sensowności: maksimum w rozsądnym zakresie i aktualnie <= maksimum.
    """
    kotwice = list(re.finditer(r"OS[ÓO]B\s+NA\s+BASENIE", tekst, re.IGNORECASE))
    if not kotwice:
        raise LicznikNieczytelny(
            "Nie znaleziono napisu 'OSÓB NA BASENIE' na stronie. "
            f"Początek tekstu strony: „{tekst[:300]}”"
        )

    fragmenty = []
    for kotwica in kotwice:
        okno = tekst[kotwica.end(): kotwica.end() + MAKS_OKNO_ZNAKOW]
        fragmenty.append(okno.strip())
        for m in re.finditer(r"(\d{1,4})\s*/\s*(\d{1,4})", okno):
            aktualnie, maksimum = int(m.group(1)), int(m.group(2))
            if not (MAKS_POJEMNOSC_MIN <= maksimum <= MAKS_POJEMNOSC_MAX):
                continue
            if aktualnie > maksimum:
                continue
            pominiete = okno[: m.start()].strip()
            if pominiete:
                print(
                    f"UWAGA: przed licznikiem {aktualnie}/{maksimum} na stronie jest "
                    f"dodatkowy tekst, który pomijam: „{pominiete}”",
                    file=sys.stderr,
                )
            return aktualnie, maksimum

    raise LicznikNieczytelny(
        "Przy napisie 'OSÓB NA BASENIE' nie ma poprawnego licznika 'X/Y'. "
        "Fragmenty strony za napisem: " + " | ".join(f"„{f}”" for f in fragmenty)
    )


def pobierz_dane(proby=3, opoznienie_sek=5):
    """Pobiera stronę i wyciąga parę liczb 'aktualnie/maksimum'.

    Ponawia próbę kilka razy w razie chwilowych problemów sieciowych
    (timeout, strona chwilowo niedostępna itp.). Jeśli strona wprost
    informuje, że basen jest zamknięty (dzień sanitarny, przerwa
    techniczna itp.), od razu zgłasza to jako BasenZamkniety —
    bez sensu ponawiać próby w takiej sytuacji.
    """
    ostatni_blad = None
    for proba in range(1, proby + 1):
        try:
            resp = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            html_tresc = resp.text

            # Usuwamy znaczniki HTML, dekodujemy encje (np. &nbsp;, &oacute;)
            # i normalizujemy białe znaki — strona bywa różnie sformatowana
            # (np. "80/80" albo "80 / 80" z niełamliwą spacją).
            html_tresc = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html_tresc)
            html_tresc = re.sub(r"(?s)<!--.*?-->", " ", html_tresc)
            tekst = re.sub(r"<[^>]+>", " ", html_tresc)
            tekst = html.unescape(tekst)
            tekst = re.sub(r"\s+", " ", tekst)

            tekst_upper = tekst.upper()
            for fraza in FRAZY_ZAMKNIECIA:
                if fraza in tekst_upper:
                    raise BasenZamkniety(f"Strona sygnalizuje zamknięcie basenu: „{fraza}”")

            return wyciagnij_licznik(tekst)

        except (BasenZamkniety, LicznikNieczytelny):
            raise  # strona się pobrała, ponawianie nic nie zmieni

        except Exception as e:
            ostatni_blad = e
            print(f"Próba {proba}/{proby} pobrania strony nieudana: {e}", file=sys.stderr)
            if proba < proby:
                time.sleep(opoznienie_sek)

    raise RuntimeError(f"Nie udało się pobrać danych po {proby} próbach: {ostatni_blad}")


def pobierz_pogode():
    """Pobiera aktualną temperaturę i opis warunków dla Łańcuta z Open-Meteo.

    Nie ma klucza API i jest w pełni darmowe. W razie problemu (API padło,
    timeout) zwraca puste stringi — brak pogody nie powinien nigdy zablokować
    zapisu samej frekwencji, to dane poboczne.
    """
    try:
        resp = requests.get(POGODA_URL, timeout=10)
        resp.raise_for_status()
        dane = resp.json().get("current_weather", {})
        temperatura = dane.get("temperature", "")
        kod = dane.get("weathercode")
        if kod is None:
            warunki = ""
        else:
            opis = KODY_POGODY.get(kod, "Nieznane")
            warunki = f"{kod} - {opis}"
        return temperatura, warunki
    except Exception as e:
        print(f"Nie udało się pobrać pogody (pomijam): {e}", file=sys.stderr)
        return "", ""


def w_oknie_godzinowym(teraz):
    return GODZINA_START <= teraz.hour < GODZINA_KONIEC


def zapisz(aktualnie, maksimum, temperatura, warunki, teraz):
    nowy_plik = not os.path.exists(DATA_FILE)
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if nowy_plik:
            writer.writerow(
                ["timestamp_pl", "data", "godzina", "minuta", "osoby", "maksimum", "temperatura", "warunki"]
            )
        writer.writerow(
            [
                teraz.strftime("%Y-%m-%d %H:%M:%S"),
                teraz.strftime("%Y-%m-%d"),
                teraz.hour,
                teraz.minute,
                aktualnie,
                maksimum,
                temperatura,
                warunki,
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
    except BasenZamkniety as e:
        print(f"{teraz.strftime('%Y-%m-%d %H:%M')} czasu PL -> {e} — pomijam zapis.")
        return
    except LicznikNieczytelny as e:
        # Strona działa, ale ktoś wpisał na niej coś nieczytelnego — to nie awaria
        # skryptu. Pomijamy pomiar (bez czerwonego przebiegu), a szczegóły są w logu.
        print(f"::warning::Licznik nieczytelny, pomijam pomiar. {e}")
        print(f"{teraz.strftime('%Y-%m-%d %H:%M')} czasu PL -> licznik nieczytelny — pomijam zapis.")
        return
    except Exception as e:
        print(f"Błąd pobierania danych: {e}", file=sys.stderr)
        sys.exit(1)

    temperatura, warunki = pobierz_pogode()

    zapisz(aktualnie, maksimum, temperatura, warunki, teraz)
    print(
        f"{teraz.strftime('%Y-%m-%d %H:%M')} czasu PL -> "
        f"{aktualnie}/{maksimum} osób na basenie, {temperatura}°C, {warunki} "
        f"(zapisano do {DATA_FILE})"
    )


if __name__ == "__main__":
    main()
