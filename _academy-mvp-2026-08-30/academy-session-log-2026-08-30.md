# Academy MVP — záznam sezení (2026-08-30)

*Co se v tomhle sezení probralo a rozhodlo, aby na to šlo navázat v jakékoli další konverzaci v projektu. Detaily jsou ve dvou souvisejících dokumentech, tenhle je rozcestník a zápis rozhodnutí.*

## Související dokumenty v projektu

- `claude/academy-implementation-plan-2026-08-30.md` — inspekce codebase + plán implementace
- `claude/academy-build-handover-2026-08-30.md` — co bylo postaveno, jak to nasadit, co se ověřilo
- `claude/academy-mvp-source-2026-08-30.patch.md` — samotný patch (text, dá se přímo `git apply`)

## Zadání

Petr nahrál `mtor_atlas_academy_claude_implementation_spec_v2.pdf` (Academy / Learn MVP — UX/UI + implementační spec, 21 sekcí) a zadal: nejdřív prozkoumat celou existující codebase Atlasu bez jediné změny, pak navrhnout co nejméně invazivní implementaci.

## Co se zjistilo o Atlasu

- **Žádný framework.** Vanilla HTML/CSS/JS generované a patchované Pythonem. Tři vrstvy: SPA (`index.html`, 3,3 MB, hash router), statický pre-render (~390 stránek z `build_pages.py`, plus `/answers/` + `/glossary/` z `generate.py`), a lazy modul `pathway/`.
- **Guided Routes nemají vlastní URL.** Je to jeden ze čtyř režimů uvnitř tabu Pathway. Nejhlubší adresa, která existovala, byla `#view=map&pw=guided`. Přitom těch 11 tras je obsahově to nejlepší, co Atlas má — každá má otázku v názvu, `story`, `journey` a kroky s `what`/`why`.
- **`deploy.bat` stageuje složky podle výslovného seznamu.** Nová složka, která v tom seznamu není, se nikdy nedostane na web. V komentářích samotného souboru jsou zaznamenané dva případy, kdy se to už stalo.
- Ze spec §8 dva ze žádaných tokenů už existují (statické stránky mají 760 px sloupec a 16 px/1,6 text). Kolidoval jen radius karet.

## Rozhodnutí (potvrzena Petrem)

1. **Architektura:** statický generátor `build_academy.py` → skutečné adresy `/academy/core/rheb`. Ne devátý pohled SPA.
2. **Guided Routes:** přidat aditivní parametr `&route=<id>` + `PathwayApp.openRoute(id)`. Dosavadní URL se nemění.
3. **Radius karet:** zůstávají ostré rohy Atlasu (3 px). Spec §8 se sama podřizuje existujícímu design systému.
4. **Kalibrační brána:** rozšířit `validate_claims.py` i na prózu lekcí, ve stejné `--strict` bráně.

## Co bylo postaveno

5 stránek (`/academy/`, `/academy/core/`, tři lekce), generátor sdílející `build_pages.shell()`, nová brána `verify_academy.py`. Lekce ukládají **jen ID** — názvy studií, roky, tiery a findings se resolvují při buildu z `studies_baked.json`, takže se nikde nekopíruje vědecká databáze.

Zásah do `index.html`: **4 hunky, +23/−4.** Položka LEARN je `<a>`, ne `data-tab` div, takže se `showView`/`applyHash`/`syncURL` nemusely vůbec dotknout.

## Dva nálezy mimo zadání

- **`deploy.bat` nikdy nespouštěl `stamp_pathway_version.py`.** `deploy.sh` ano. Bez toho by windowsí deploy poslal nový `pathway.js` se starým `?v=` hashem a CDN by dál servírovala starý modul — přesně ta chyba, kvůli které ten skript vznikl po incidentu ve Fázi 1. Doplněno.
- **`#view=map` loguje `<svg> viewBox: -Infinity`.** Ověřeno proti nezměněnému `main`: je to starší chyba, ne regrese. Web funguje, ale je to reálný bug v kameře pathway modulu, když fituje prázdný bounding box. Nedotčeno, čeká na rozhodnutí.

## Stav a co dál

Práce je hotová a ověřená (všechny deploy brány + smoke test 2699/2699 + prohlížečová regrese), ale **nebyla pushnuta** — proxy tohohle sezení nemá `open-mtor-atlas/atlas` v autorizované sadě repozitářů. Aplikuje se patchem nebo git bundlem.

Otevřené volby pro příští krok:
- opravit ten `-Infinity` bug v pathway kameře;
- dopsat lekce 04–10 (v kurikulu už jsou vypsané a označené *in preparation*);
- přidat `open-mtor-atlas/atlas` do zdrojů sezení, ať jde příště pushnout přímo.

**Přidání další lekce** je levné: zapsat ji do `academy_data/lessons.json`, přepnout `status` na `published` v `modules.json`, opravit `previousLesson`/`nextLesson` u sousedů, spustit `build_academy.py` a `verify_academy.py`. Nic jiného — žádný nový soubor stránky, žádná úprava šablony, navigace ani deploye.
