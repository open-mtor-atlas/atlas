## Imported Claude Cowork project instructions

## Autori: lab_name je povinny

- Kazdy novy medailonek v `atlas_data/author_bios_baked.json` musi mit `lab_name` ve formatu `Nazev laboratore, instituce (mesto, stat, zeme)` (u Cinske a evropskych zemi bez statu, napr. `(Ganzhou, China)`), a kdyz je overeny, i `lab_url`.
- Lab map se pregeneruje pri kazdem buildu (`build_lab_map.py`, volany z `deploy.bat`). Medailonek bez lab_name nebo mesto bez souradnic vypise VAROVANI; nove mesto se zkusi geokodovat, jinak doplnit do `atlas_data/lab_geo.json`.
