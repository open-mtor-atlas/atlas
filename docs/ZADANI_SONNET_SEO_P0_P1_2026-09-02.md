# Zadání pro Claude Sonnet — SEO/GEO fáze P0→P1 Atlasu (autonomní exekuce, bez e-mailů)

*Připraveno 2. 9. 2026 na základě `claude/seo-geo-strategie-kriticke-zhodnoceni-2026-09-02.md`. Tento dokument je určený jako kompletní prompt/brief pro samostatnou session Claude Sonnet nad repem Atlasu. Úkoly jsou seřazené podle priority; každý má jasné vstupy, kroky a kritéria hotovosti. Nic z toho nevyžaduje odeslání e-mailu ani veřejnou publikaci na cizí platformě bez souhlasu Petra.*

---

## 0. Role, kontext, pravidla

**Role:** Jsi inženýr/kurátor pracující na webu **Oliver's mTOR Atlas** (https://mtor-atlas.org, statický web na GitHub Pages, generovaný z `build_pages.py`, `build_academy.py`, `generate.py` nad `atlas_data/*.json`). Tvůj cíl je zvýšit vnímanou kvalitu domény pro Google a citovatelnost pro AI vyhledávače a biomedicínskou komunitu. Pracuješ v repu `C:\Users\petr.barton\Documents\Claude\Projects\Oliver biology Cowork` (v Cowork VM je připojené jako `$HOME/mnt/Oliver biology Cowork`).

**Proč to děláme (jednou větou):** ~70 % URL webu jsou study stránky, které jsou z ~80 % textu doslovný abstrakt z PubMedu — Google to čte jako tenký/duplicitní obsah a proto indexuje jen ~74 z ~343 stránek. Registrace a odkazy nepomohou, dokud se tohle nezmění.

**Tvrdá pravidla (neporušovat):**
1. **Neodesílej e-maily, neposílej formuláře na cizí weby, nezakládej účty, nepublikuj posty, neotvírej PR/issues v cizích repozitářích.** Vše, co takový krok vyžaduje, jen **připrav jako soubor** do `outreach/` a napiš do handoveru, co má Petr/Oliver kliknout.
2. **Nepushuj na `main`.** Pracuj na větvi `seo-p0-2026-09` (vytvoř z aktuálního `main`). Commituj po každém hotovém úkolu s popisnou zprávou. Deploy (`deploy.bat`) dělá Petr na Windows — z Linux VM ho spustit nejde.
3. **`index.html` (3,4 MB) nikdy needituj nástrojem Edit** — truncuje konec souboru. Používej Python: načti, uprav, zapiš přes `os.write` + `fsync`, ověř délku a `</html>` na konci, spusť `verify_index_html.py index.html`. (Viz projektová paměť `index-html-large-file-writes`.)
4. **`pathway/model.json` needituj ručně** — je to jediný zdroj biologie dráhy; čti ho, nepiš.
5. **Nezvyšuj počet stránek** — žádné nové entity stránky pod prahem `PAGE_THRESHOLD = 3`, žádné per-study „mini stránky". Cílem je vyšší poměr skutečného obsahu k počtu URL, ne víc URL.
6. **Nikam nedávej odkaz na GitHub repo** (rozhodnutí Petra 30.–31. 8.). `sameAs` a patičky ho záměrně nemají. Výjimka: `outreach/` drafty pro formální žádosti (LinkOut, Bioregistry), kde je URL repa standardní součást — označ to v handoveru.
7. **Nepiš Google Scholar `citation_*` meta tagy** na lekce, answers ani study stránky (Scholar to vylučuje a u study stránek by to bylo mylné přiřazení autorství).
8. **Evidence tier = typ studie, ne známka kvality.** Paleta A–D má stejnou luminanci, hlídá `check_tier_palette.py` — spusť ho po každé změně CSS.
9. Pomocné skripty piš do `$HOME/seo-work/` nebo `tools/seo/` v repu, ne do `/tmp` (kolize se starými soubory jiných sezení).
10. Pokud něco nejde ověřit (síť VM nemá egress na většinu domén), napiš to do handoveru jako „neověřeno", nikdy nepředstírej.

**Ověřovací sekvence před commitem** (replikace `deploy.bat`, v tomto pořadí): `stamp_updated.py` → `build_academy.py` → `build_pages.py` → `stamp_pathway_version.py` → `node prerender_tabs.js` → `verify_prerender.py` → `validate_claims.py --strict --json atlas_data/claim_validation.json` → `verify_index_html.py index.html` → `check_tier_palette.py`. Obří diff (~460 souborů s novým timestampem v patičce) je normální.

**Na konci každého úkolu** doplň řádek do `docs/SEO_P0_HANDOVER_2026-09.md` (vytvoř): co se změnilo, které soubory, jak ověřeno, co zbývá na Petra.

---

## Úkol 1 — Změřit, jak tenké study stránky opravdu jsou (30 min)

**Vstup:** `study/*/index.html` (354), `atlas_data/studies_baked.json`.

**Kroky:**
1. Napiš `tools/seo/measure_study_pages.py`: pro každou study stránku odstraň `<script>`, `<style>`, tagy; spočítej celkový počet znaků textu, délku abstraktu (`abstract` pole), délku unikátního kurátorského textu (`finding` + „Extracted findings" řádky + tagy entit), počet odkazů na entity/answers/academy.
2. Výstup `atlas_data/seo_study_audit.csv` (sid, tier, chars_total, chars_abstract, chars_unique, ratio_unique, n_entity_links, has_extracted, has_academy_link) + shrnutí do handoveru: medián `ratio_unique`, kolik stránek má `chars_unique < 400`, kolik má 0 odkazů na entity.

**Hotovo, když:** CSV existuje a handover má tabulku „počet stránek podle pásma unikátního obsahu (<200 / 200–400 / 400–800 / >800 znaků)".

---

## Úkol 2 — Přestavět šablonu study stránky: kurátorský záznam nahoru, abstrakt zkrátit (největší páka)

**Vstup:** `build_pages.py::study_page()` (řádek ~581), `atlas_data/studies_baked.json`, `atlas_gaps/studies_enriched.jsonl` (deep-extrahovaná fakta: dávka, n, effect size, limitations — nejsou v baked JSONu, je jich 250), `atlas_data/gaps_baked.json`, `answers/*/index.html`, `academy/` index (funkce `_load_academy_index`).

**Nová struktura stránky (v tomto pořadí):**
1. H1 titul, meta řádek (autoři · rok · journal · Atlas ID) — beze změny.
2. **„What this study shows"** — `finding` jako první odstavec (už je), plus **jedna věta „Why tier X"**: generuj z `pyramid`/`category`/`model` šablonou typu „Tier C because it is a mouse intervention study (model: C57BL/6 mice); tier describes study design, not quality." — 6–8 šablon podle tieru a typu, ne jednu generickou.
3. **Extracted findings** — rozšiř o pole z `atlas_gaps/studies_enriched.jsonl` (dose, sample size, effect size, limitations), joinuj podle `Study_ID`/`sid`. Zobrazuj VŽDY, když existuje aspoň jedno pole (dnes se tabulka objeví jen při `ai_effect`/`ai_intervention`). Odstraň `lv-hide-beginner` z této sekce — extrahované nálezy jsou to nejcennější i pro začátečníka.
4. **„In the Atlas"** — odkazy: entity (už jsou jako tagy; přejmenuj sekci a dej výš), **otázky z `gaps_baked.json`, které tuto studii citují** (podle SID v poli studií), **answers stránky, které ji citují** (grep SID/DOI v `answers/*/index.html`), lekce Academy (už je). Každý odkaz s jednou větou kontextu, ne holý seznam.
5. **Abstract** — zkrať na prvních ~600 znaků (ukonči na hranici věty) + odkaz „Read the full abstract on PubMed →" (PMID) nebo na DOI. V JSON-LD `abstract` nech plný text (strojově je to v pořádku a Google to nepočítá jako viditelný duplicitní obsah). Přesuň sekci **pod** „In the Atlas".
6. **„Cite this record"** — blok s APA + BibTeX citací Atlas záznamu (ne původní studie): `Barton, O. (2026). [Title] — evidence-graded record [SID]. In Oliver's mTOR Atlas. https://mtor-atlas.org/study/SID/ · Dataset DOI 10.5281/zenodo.22059963`. Bez JS, čistý `<pre>`.
7. Patička: viditelné **„Record last updated: YYYY-MM-DD"** — datum vezmi z `atlas_data/AUDIT_changelog_studies.json` / `REVIEW_changelog_studies.json`, pokud tam SID je; jinak `date-released` z `CITATION.cff`. Do JSON-LD přidej `dateModified` se stejnou hodnotou. **Ne** build timestamp (ten by měnil všechny stránky každý deploy — `write()` to řeší záměrně).

**Noindex pro záznamy bez kurátorského obsahu:** po přestavbě znovu spusť `measure_study_pages.py`. Stránky, kde `chars_unique < 250` **a** `n_entity_links == 0` **a** nemají extracted findings, dostanou `<meta name="robots" content="noindex, follow">` a vypadnou ze `sitemap-studies.xml` (parametr v `study_page`, seznam SID ulož do `atlas_data/seo_noindex_studies.json`, ať je to reverzibilní). Do handoveru napiš počet a seznam — Petr/Oliver rozhodnou, jestli je doplní kurátorsky, nebo nechají noindex.

**Hotovo, když:** `build_pages.py` projde, náhodný vzorek 5 stránek (tier A, B, C, D, review bez extrakce) vypadá správně ve světlém i tmavém režimu (screenshot přes headless Playwright, `_ui-baseline/` má harness), medián `ratio_unique` v novém auditu vzrostl aspoň 2×, validátory prošly, commit.

---

## Úkol 3 — Data ke stažení na webu + Dataset schema s `distribution.contentUrl`

**Vstup:** `atlas_data/studies_baked.json`, `entities_baked.json`, `gaps_baked.json`, `pathway/model.json`, `atlas_data/relation_candidates.csv` (jen `REVIEWED` řádky), `CITATION.cff` (verze), `build_pages.py::data_page()` + `DATASET_REF`.

**Kroky:**
1. Napiš `build_data_exports.py` (volaný z `build_pages.py::main()` před `data_page`): vygeneruje do `data/` soubory `atlas-studies.csv`, `atlas-studies.json`, `atlas-entities.json`, `atlas-open-questions.json`, `atlas-pathway-model.json` (kopie modelu), `atlas-relations.csv`, `README.txt` (licence CC BY 4.0, citace, verze, datum, popis sloupců). CSV s UTF-8 BOM (Excel), sloupce: sid, title, authors, year, journal, doi, pmid, pmcid, tier, tier_label, pyramid, category, model, finding, ai_intervention, ai_target, ai_species, ai_effect, entities (|-separated), url. **Bez abstraktů** (licenčně čisté; abstrakt je na PubMedu).
2. `/data/` stránka: tabulka „Download" s velikostí, formátem, počtem řádků, checksum SHA-256.
3. `DATASET_REF` a JSON-LD na `/data/` a homepage: `distribution` = pole `DataDownload` s `contentUrl`, `encodingFormat` (`text/csv`, `application/json`), `contentSize`; doplň `isAccessibleForFree: true`, `version` (z CITATION.cff), `variableMeasured` (evidence tier, study design, intervention, target, effect), `temporalCoverage` (min–max rok studií), `keywords`. Validuj JSON-LD lokálně (`json.loads`) a strukturu proti https://developers.google.com/search/docs/appearance/structured-data/dataset (povinné `name`, `description` 50–5000 znaků).
4. Přidej `data/` exporty do seznamu souborů, které `deploy.bat` přidává do gitu (zkontroluj `git add` sekci — historicky tam chyběly nové adresáře; viz paměť `static-pages-git-add-gap`). `deploy.bat` pak **commitni explicitně** (není ve vlastním add seznamu a má gate na shodu s origin).
5. Připrav **Hugging Face dataset card** `outreach/huggingface/README.md` (YAML frontmatter: license cc-by-4.0, task_categories, tags mtor/biology/curated-literature, `citation` s DOI) + skript `outreach/huggingface/upload.py` (huggingface_hub, čte token z env). **Nespouštěj** — Petr rozhodne o účtu. Totéž pro Kaggle (`outreach/kaggle/dataset-metadata.json`).

**Hotovo, když:** soubory jsou v `data/`, `/data/` stránka na ně odkazuje, JSON-LD validní, `README.txt` popisuje sloupce, commit.

---

## Úkol 4 — Statická homepage, SPA na `/app/`

**Vstup:** `index.html` (SPA, 3,4 MB), `patch_home()` a `patch_spa_links()` v `build_pages.py`, `node prerender_tabs.js` + `verify_prerender.py` (existující prerender tabů — zjisti, co přesně dělá, než něco duplikuješ), `CNAME`, `answers/index.html`, `about/`, `sitemap-home.xml`.

**Zásada:** Nejdřív **navrhni** do handoveru dvě varianty a jejich rizika, pak implementuj **jen variantu A**, pokud ji nic neblokuje:
- **Varianta A (preferovaná):** SPA přesunout do `/app/index.html` (beze změny obsahu), na `/` dát lehkou statickou stránku generovanou z `build_pages.py` (`home_page()`): co Atlas je (3 věty), čísla (studie, entity, otázky, lekce — živě z dat), šest vstupů (Browse, Answers, Academy, Pathway/App, Data, About), tři nejsilnější answers s TL;DR větou, poslední přidané studie (5), blok „How to cite", Dataset JSON-LD. Cíl < 150 KB bez fontů. Všechny existující odkazy tvaru `/#view=...`, `/#studies` apod. musí dál fungovat: na `/` malý inline skript, který při přítomnosti `#`-fragmentu přesměruje na `/app/#...` (crawler bez JS vidí statický obsah, člověk s deep-linkem skončí v aplikaci). Aktualizuj `SITE_TABS`/`topbar_html`, patičky, `llms.txt`, `sitemap-home.xml` (přidat `/app/`), `robots.txt` beze změny.
- **Varianta B (fallback):** SPA zůstane na `/`, ale do `index.html` se před první `<script>` vloží statický „above the fold" blok s týmž obsahem (ne skrytý, viditelný do doby, než JS vykreslí aplikaci). Použij jen, když A rozbije něco, co nejde spravit (např. GA4/Plausible konfigurace vázaná na cestu, OG obrázky, IndexNow klíč).

**Hotovo, když:** `/` je statická, `/app/` funguje s deep-linky (ověř headless Playwright: `/#studies` → `/app/#studies`, tab se otevře), `verify_index_html.py` prošel na `app/index.html` (uprav cestu ve skriptu/deploy.bat), Lighthouse/Playwright metrika: `/` DOM content < 200 KB, commit.

---

## Úkol 5 — Statické `/pathway/`, `/mechanism/`, `/events/`

**Vstup:** `pathway/model.json` (nodes, interactions, compartments, routes, loops, open_loops), `atlas_data/relation_candidates*.csv` (řádky `REVIEWED` se `SIGN`) nebo Airtable Relations dump v `atlas_data/` (43 podepsaných vztahů — dohledej, kde jsou bakované; pokud jen v `index.html` JS objektu, vyexportuj je skriptem stejně jako se dělalo s `AUTHOR_BIOS`), `atlas_data/events_baked.json` (39 akcí), `pathway.js` (jak SPA kreslí diagram).

**Kroky:**
1. `/pathway/`: statický SVG diagram dráhy vykreslený z modelu (headless Playwright nad existujícím `pathway.js` → `outerHTML` SVG, nebo vlastní jednoduchý layout z `compartments`/`bands`), uložený jako `pathway/mtor-pathway.svg` + PNG 1600 px pro OG/Images. Stránka: H1 „The mTOR signaling pathway", 4 odstavce popisu vrstev (upstream inputs → TSC/Rheb → mTORC1/mTORC2 → outputs) s odkazy na entity stránky, diagram s `alt` a `figcaption`, seznam všech interakcí jako tabulka „Source → Target (effect, evidence tier, n studies)" s odkazy na study stránky, JSON-LD `ImageObject` + `CollectionPage`. Licence CC BY v caption (připravuje Wikimedia Commons upload — jen soubor, ne upload).
2. `/mechanism/`: 43 podepsaných vztahů jako samostatné, citovatelné věty: „**Rapamycin inhibits mTORC1** — supported by N studies (tiers …): [odkazy]". Seskupit podle cíle. JSON-LD: `DefinedTermSet`? ne — použij `ItemList` položek `ScholarlyArticle`-referencí; nevymýšlej nestandardní typy.
3. `/events/`: tabulka konferencí (název, datum, místo, web, vazba na autory Atlasu), JSON-LD `Event` jen pro budoucí akce s datem (Google `Event` markup vyžaduje `startDate`, `location`); minulé bez markupu.
4. Přidat do `sitemap-entities.xml` (nebo nová `sitemap-topics.xml` + index), do `SITE_TABS`, `browse/`, `llms.txt`.

**Hotovo, když:** tři stránky existují, diagram má alt a odkazy, validátory prošly, screenshot light/dark, commit.

---

## Úkol 6 — Academy: Bioschemas `TrainingMaterial` + registrační podklady (bez odeslání)

**Vstup:** `build_academy.py`, `academy/**/index.html` (14 stránek), `academy_data/`.

**Kroky:**
1. Do každé lekce JSON-LD `LearningResource` + Bioschemas profil `TrainingMaterial` (`@type: ["LearningResource","TrainingMaterial"]`, `name`, `description`, `keywords`, `learningResourceType: "e-learning"`, `educationalLevel`, `audience`, `license`, `author` (Person, ORCID 0009-0008-2025-2148), `inLanguage`, `timeRequired`, `isPartOf` kurz, `teaches`). Kurzová stránka `Course` + `CourseInstance` (online, self-paced, free) — Google Course rich result vyžaduje `hasCourseInstance` s `courseMode`.
2. Připrav `outreach/tess/atlas-academy.json` (položky pro ELIXIR TeSS registraci), `outreach/merlot/merlot-fields.md`, `outreach/oercommons/fields.md` — vyplněné texty, které Petr jen zkopíruje do formulářů.

**Hotovo, když:** markup validní (json.loads + kontrola povinných polí), commit, drafty v `outreach/`.

---

## Úkol 7 — NCBI LinkOut: kompletní balík k odeslání (bez odeslání)

**Vstup:** `atlas_data/pmid_map.json` (SID → PMID), `atlas_data/studies_baked.json`, dokumentace https://www.ncbi.nlm.nih.gov/books/NBK3812/ (formát `providerinfo.xml` a resource file; VM na ni nejspíš nedosáhne — použij formát z paměti: ProviderId placeholder, Name, NameAbbr, Url, Brief; resource CSV `PrId,DB,UID,url,IconUrl,UrlName,SubjectType,Attribute`).

**Kroky:**
1. `tools/seo/build_linkout.py` → `outreach/linkout/providerinfo.xml`, `outreach/linkout/resources.csv` (jen studie s PMID; `url` = `https://mtor-atlas.org/study/{SID}/`, `UrlName` = „Evidence-graded record in Oliver's mTOR Atlas", `SubjectType` = `research databases`? — použij hodnoty ze seznamu povolených atributů v dokumentaci, pokud ji získáš; jinak označ jako TODO).
2. `outreach/linkout/application-email.md` — text žádosti na linkout@ncbi.nlm.nih.gov: popis zdroje, nekomerční, CC BY, FAIRsharing 8905, bio.tools, DOI, 5 ukázkových PMID → URL, kontakt Oliver. **Neodesílej.**
3. Ikona 16×16 / 100×20 PNG pro LinkOut z `brand/`.

**Hotovo, když:** tři soubory + ikona existují, CSV má ≥ 300 řádků, handover říká „Petr: odeslat e-mail, po schválení FTP".

---

## Úkol 8 — Registrační drafty pro Bioregistry, Database Commons, NAR DB Collection, Wikidata doplnění (bez odeslání)

1. `outreach/bioregistry/new-prefix.md`: pole podle GitHub issue šablony Bioregistry (prefix `mtoratlas`, name, homepage, URI pattern `https://mtor-atlas.org/study/$1/`, example `ABR2026`, pattern `^[A-Z]+\d{4}[A-Z]?$` — ověř regexem nad všemi SID, license, contact ORCID).
2. `outreach/database-commons/fields.md`: čtyři sekce dle jejich kurátorského modelu (basic info, data, access, publication → DOI Zenodo).
3. `outreach/nar-db-collection/summary.md`: souhrn dle šablony NAR (name, URL, description ≤ 100 slov, category „Literature / Pathways", contact).
4. `outreach/wikidata/Q141256074-additions.md`: přesná tvrzení k doplnění — bio.tools ID (property P? — dohledej přesné ID property „bio.tools ID" a „FAIRsharing ID" **jen pokud VM dosáhne na wikidata.org**; jinak napiš „ověřit property ID"), hodnoty `olivers_mtor_atlas` a `8905`.

**Hotovo, když:** čtyři soubory existují, žádné odesláno.

---

## Úkol 9 — Preprint pro Research Square: manuskript připravený k nahrání (bez nahrání)

**Vstup:** `claude/osf-preprint-draft-2026-08-29.md` a `claude/f1000research-draft-2026-09-01.md` (v projektu Claude — pokud k nim nemáš přístup, Petr ti je vloží), `atlas_data/studies_baked.json`, `atlas_data/claim_validation.json`, `AUDIT_scientific_calibration_2026-07-29.md`, `REVIEW_external_scientific_2026-07-29.md`.

**Kroky:**
1. Přepiš draft jako **„Resource / Software description"** (ne Data Descriptor): Abstract, Background, Resource description (corpus, tiering, knowledge graph, gap-finding, RAG, Academy), **Evaluation** (nová sekce — spočítej z dat: rozdělení tierů, pokrytí PMID/PMCID, počet entit nad prahem, počet validovaných tvrzení z `claim_validation.json`, výsledky externího review z července — počet nálezů a opravených), Limitations, Availability (URL, DOI, licence, bio.tools, FAIRsharing, Wikidata), References (DOI u každé).
2. Vygeneruj `outreach/research-square/manuscript.docx` (python-docx) + `manuscript.md`; titulní strana s ORCID, declarations (funding none, competing interests none).
3. `outreach/research-square/submission-checklist.md`: účet, kategorie (Life Sciences → Cell Biology / Bioinformatics), licence CC BY, co kliknout.

**Hotovo, když:** DOCX se otevře, Evaluation obsahuje jen čísla spočítaná z dat (žádné odhady), handover uvádí „Petr/Oliver: nahrát".

---

## Úkol 10 — Baseline AI citací a Bing (jen pokud máš prohlížeč)

Pokud máš k dispozici Claude in Chrome / vestavěný prohlížeč: proveď 10 dotazů (`does rapamycin extend lifespan in humans`, `mTORC1 vs mTORC2 difference`, `list of mTOR inhibitors`, `what is Rheb`, `is autophagy required for rapamycin lifespan extension`, `rapamycin vs metformin longevity`, `what does TSC2 do in mTOR signaling`, `mTOR pathway diagram`, `evidence-graded mTOR database`, `Oliver's mTOR Atlas`) v Perplexity, ChatGPT search, Google AI Mode, Bing Copilot; zapiš do `docs/AI_CITATION_BASELINE_2026-09.md` tabulku: dotaz × engine × cituje Atlas (ano/ne, URL) × které domény cituje místo něj. **Nepřihlašuj se nikam, nezakládej účty.** Bing Webmaster Tools: **nezakládej** — napiš do handoveru přesný postup (přihlásit Microsoft účtem, přidat `mtor-atlas.org`, ověřit DNS TXT nebo importem z GSC, nahrát `sitemap.xml`, zkontrolovat IndexNow historii po 3 dnech). Bez prohlížeče úkol přeskoč a zapiš to.

---

## Úkol 11 — Drobné technické položky

1. `llms.txt`: aktualizovat čísla a přidat `/data/`, `/pathway/`, `/mechanism/`, `/events/`. (Nepřeceňovat, ale udržovat.)
2. GitHub topics: připrav seznam do handoveru (`mtor`, `pathway-database`, `knowledge-graph`, `biocuration`, `evidence-synthesis`, `aging-biology`) — nastavuje Petr v UI.
3. `/about/`: přidat odstavec „Corrections log" s odkazem na veřejný changelog — vygeneruj `/changelog/` z `atlas_data/AUDIT_changelog_*.json` + `REVIEW_changelog_studies.json` (datum, SID, co se změnilo, jednou větou). Je to E-E-A-T signál, který audit z 23. 8. označil za chybějící.
4. Cross-link: každá `/answers/` stránka odkazuje na `/question/` protějšek a naopak — ověř, že to platí po přestavbě (audit 29. 8. našel jednosměrnost).

---

## Co NEDĚLAT v této session

Neposílat e-maily; nezakládat účty; nezakládat PR/issues v cizích repech; nepřidávat entity stránky; neposílat Request Indexing v GSC; nepsat další Reddit/HN posty; neměnit `pathway/model.json`; neměnit evidence tier dat; nepushovat na `main`; nepouštět `deploy.bat`.

## Výstup session

1. Větev `seo-p0-2026-09` s commity po úkolech (1→11), všechny validátory zelené.
2. `docs/SEO_P0_HANDOVER_2026-09.md`: pro každý úkol stav (hotovo / částečně / přeskočeno + proč), čísla před/po z Úkolu 1 vs. po Úkolu 2, seznam noindex SID k rozhodnutí, a **přesný seznam kroků pro Petra** (merge + `deploy_with_pathway_refresh.bat`, odeslání LinkOut e-mailu, nahrání Research Square, HF/Kaggle účet, Bing WMT, TeSS/MERLOT/OER formuláře, Bioregistry issue, Database Commons, NAR summary, Wikidata doplnění, GitHub topics).
3. `outreach/` se všemi drafty; nic z něj nebylo odesláno.
