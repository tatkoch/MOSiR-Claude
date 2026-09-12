# Monitor obłożenia basenu MOSiR Łańcut

Automatyczne zbieranie danych o liczbie osób na basenie krytym MOSiR Łańcut
(strona `https://mosir-lancut.pl/asp/...menu=135...`) i wizualizacja w Google Colab.

## Jak to działa

1. **`scrape.py`** — pobiera stronę, wyciąga liczbę „X/Y osób na basenie”
   i dopisuje wiersz do `data/basen_dane.csv`. Jeśli aktualna godzina (czasu
   polskiego) jest poza 6:00–22:00, nic nie zapisuje.
2. **`.github/workflows/scrape.yml`** — uruchamia `scrape.py` co 15 minut,
   przez cały rok, i sam zapisuje (commituje) nowe dane z powrotem do repo.
   Działa całkowicie za darmo w GitHub Actions, nie potrzebujesz żadnego
   serwera ani włączonego komputera.
3. **`wizualizacja_colab.ipynb`** — notebook do wgrania na Google Colab,
   który wczytuje `data/basen_dane.csv` bezpośrednio z GitHuba i rysuje
   wykresy (trend w czasie, heatmapa dzień/godzina, średnia wg godziny).

## Konfiguracja krok po kroku

### 1. Załóż repozytorium na GitHubie
- Wejdź na github.com → **New repository** (może być prywatne lub publiczne).
- Wgraj do niego wszystkie pliki z tego folderu, zachowując strukturę
  (ważne, żeby `.github/workflows/scrape.yml` trafił dokładnie tam,
  z zachowaniem tej ścieżki).

### 2. Włącz uprawnienia do zapisu dla Actions
GitHub domyślnie blokuje workflow'om możliwość commitowania zmian. Trzeba to
odblokować:
- W repo: **Settings → Actions → General → Workflow permissions**
- Zaznacz **„Read and write permissions”** → **Save**

### 3. Sprawdź, czy harmonogram działa
- Zakładka **Actions** w repo → powinieneś zobaczyć workflow
  „Zbieranie danych o liczbie osób na basenie”.
- Możesz go od razu odpalić ręcznie (**Run workflow**), żeby sprawdzić, czy
  wszystko działa, zamiast czekać na najbliższe 15 minut.
- Uwaga: harmonogramy (`cron`) w GitHub Actions to zadania z „najlepszych
  starań” — czasem uruchomią się z kilkuminutowym opóźnieniem, szczególnie
  gdy GitHub ma dużo ruchu. To normalne i nie wpływa istotnie na dane.

### 4. Podłącz Google Colab
- Wejdź na [colab.research.google.com](https://colab.research.google.com),
  **Upload notebook** → wybierz `wizualizacja_colab.ipynb`.
- W pierwszej komórce podmień:
  ```python
  RAW_CSV_URL = "https://raw.githubusercontent.com/TWOJ_LOGIN/NAZWA_REPO/main/data/basen_dane.csv"
  ```
  na prawdziwy link do Twojego pliku (na GitHubie otwórz `data/basen_dane.csv`,
  kliknij przycisk **Raw** i skopiuj adres z paska przeglądarki).
- Uruchom wszystkie komórki (**Runtime → Run all**). Za każdym razem, gdy
  odpalisz notebook ponownie, pobierze najświeższe dane z repo.

## Ważne uwagi

- **Legalność/regulamin strony**: to publicznie dostępna strona informacyjna
  MOSiR, a skrypt tylko odczytuje ją co 15 minut (mniejszy ruch niż zwykłe
  odświeżanie przez przeglądarkę) — jeśli chcesz zbierać dane bardzo długo
  lub bardzo często, warto zerknąć na regulamin strony/robots.txt albo po
  prostu zapytać MOSiR, czy nie mają już własnego API/eksportu tych danych.
- **Struktura strony może się zmienić** — jeśli MOSiR przebuduje stronę,
  regex w `scrape.py` (`OSÓB NA BASENIE (\d+)/(\d+)`) przestanie pasować i
  workflow zacznie kończyć się błędem. Wtedy trzeba będzie poprawić regex
  pod nowy układ strony.
- **Prywatne vs publiczne repo**: jeśli repo jest prywatne, link `raw.githubusercontent.com`
  nie zadziała bez tokenu — albo ustaw repo jako publiczne, albo pobieraj
  CSV w Colabie przez `git clone` z tokenem dostępu.
