# Fáze 6 — Nalezitelnost & rozšiřitelnost Open mTOR Atlas

**Datum:** 2026-07-27
**Stav webu při psaní:** jeden soubor `index.html` (1.33 MB), GitHub Pages, doména `mtor-atlas.org`, 270 studií, sitemap má **1 URL**.

---

## 0. Verdikt k předloženému návrhu

Návrh je **strategicky správný, ale špatně seřazený a nadhodnocený v objemu**.

### Co je v návrhu správně

| Bod | Proč sedí |
|---|---|
| Jedna URL na téma | Bez toho neexistuje nic dalšího. Kritické. |
| Schema.org (`Dataset`, `ScholarlyArticle`) | Vstupenka do Google Dataset Search. |
| Evidence bloky / strukturovaný obsah | Přesně to, co LLM umí citovat. |
| E-E-A-T, DOI/PMID, datum revize | V YMYL doméně (zdraví) to není bonus, je to podmínka. |
| „Stát se citovaným zdrojem" > SEO | Nejsprávnější věta celého návrhu. Viz Fáze C. |

### Co je v návrhu špatně

**1. Blokující problém, který návrh vůbec nezmiňuje: web je pro AI vyhledávače prázdný.**

Ověřeno měřením: všech 270 studií je uloženo jako JSON uvnitř `<script>`. Po odstranění skriptů zbývá v HTML **18 451 znaků** — navigace, nadpisy, marketingový text. Žádná studie, žádný abstrakt, žádný nález.

Googlebot JavaScript renderuje (s odkladem). **GPTBot, OAI-SearchBot, PerplexityBot, ClaudeBot a Common Crawl JS zpravidla nespouštějí.** Pro ně dnes Atlas neobsahuje nic. Cíl „být citován AI asistenty" tedy dnes selhává na technikálii, ne na obsahu.

→ Tohle je jediná změna s nejvyšším poměrem dopad/úsilí v celém dokumentu. Vše ostatní je až za ní.

**2. „Tisíce stránek" je z 270 studií nerealizovatelné a aktivně nebezpečné.**

Skutečná čísla z `studies_baked.json`:

```
ai_target        208 unikátních hodnot / 270 studií
ai_intervention  212 unikátních hodnot / 270 studií
ai_species       138 unikátních hodnot / 270 studií
tier             D=182, C=59, B=25, A=1
```

Medián entity má **jednu** studii. Stránka `/proteins/x` s jednou studií tier D je definičně thin content. Google od spam update 03/2024 explicitně postihuje *scaled content abuse* — a trest je sitewide, ne per-page. Riskovat demotion celé domény kvůli 200 prázdným stránkám se nevyplatí.

Realistický strop při 270 studiích: **40–70 stránek**, které obstojí. To je stále 40–70× víc než dnešní 1.

**3. Next.js je předčasný.** SSR řeší problém, který nemáte — dynamický obsah pro přihlášené uživatele. Váš obsah se mění, když Oliver přidá studii do Airtable, tj. řádově týdně. To je **build-time**, ne request-time. Statické pre-renderování Python skriptem do stávajícího repa dá identický SEO výsledek za ~1 den práce, bez migrace hostingu, bez Node toolchainu, bez nové třídy chyb. Next.js zvažte, až budete mít >2000 stránek nebo personalizaci.

**4. Chybí předpoklad, bez kterého programmatic SEO nejde spustit: normalizace entit.** Viz Fáze A.

**5. Chybí PMID.** 270/270 studií má DOI, **0/270 má PMID**. PMID je v biomedicíně primární identifikátor pro citaci a pro propojení na Europe PMC.

**6. „AI navrhne shrnutí → kurátor zkontroluje"** — úzké hrdlo není generování, ale Oliverův čas. Pipeline navrhujte kolem revizní kapacity ~10 studií/týden, ne kolem propustnosti modelu.

---

## 1. Přepracovaný postup

Pořadí je záměrné: každá fáze odemyká další. Nepřeskakovat.

### Fáze A — Normalizace entit (předpoklad všeho)

**Problém:** `ai_target` obsahuje `"mTORC1"`, `"mTORC1 / mTORC2"`, `"mTORC1 & mTORC2"`, `"mTOR / TSC1"`, `"mTORC1 / TFEB"`. To jsou volné texty, ne entity. Z nich nelze odvodit stabilní URL, ani hranu grafu, ani `/compare` stránku.

**Řešení:** nová tabulka `Entities` v Airtable + junction tabulka `Study↔Entity` (M:N). Každá entita dostane:

| Pole | Zdroj / formát | Příklad |
|---|---|---|
| `slug` | kebab-case, **navždy neměnný** | `mtor` |
| `canonical_name` | | `MTOR` |
| `type` | gene / complex / drug / process / disease / species | `gene` |
| `synonyms` | pole textů | `mTOR, FRAP1, mechanistic target of rapamycin` |
| `xref_hgnc` | HGNC ID (geny) | `HGNC:3942` |
| `xref_chebi` / `drugbank` | léčiva | `DB00877` (sirolimus) |
| `xref_mondo` / `mesh` | nemoci | `MONDO:0004992` |
| `xref_go` | procesy | `GO:0006914` (autophagy) |

**Kroky:**
1. Skript `normalize_entities.py`: rozsekej `ai_target` / `ai_intervention` / `ai_species` na oddělovačích `/ & , +`, ořež kvalifikátory v závorkách, vyrob frekvenční seznam kandidátů.
2. Ruční mapování ~150 kandidátů → ~60–80 kanonických entit. **Toto je jediný krok, který musí udělat člověk.** Odhad 2–3 h.
3. Namapuj na externí ontologie (HGNC pro geny je zdarma přes REST, MONDO/MeSH přes OLS4). Bez xref nebudete v Wikidatech ani v Dataset Search propojení.
4. Zapiš zpět do Airtable jako links, ne texty.

**Výstup:** `atlas_data/entities_baked.json` + `study_entity_edges.json`.

> Bez Fáze A není Fáze B ani D možná. Nedělejte kompromis.

---

### Fáze B — Statické pre-renderování (největší okamžitý dopad)

Cíl: každá entita má vlastní URL s **plným obsahem v HTML**, bez JS.

1. **Build skript** `build_pages.py` čte `studies_baked.json` + `entities_baked.json` a generuje:
   ```
   /gene/mtor/index.html
   /gene/tsc2/index.html
   /drug/rapamycin/index.html
   /process/autophagy/index.html
   /disease/glioblastoma/index.html
   /study/DEM2016/index.html      ← 270 stránek, každá s unikátním abstraktem
   ```
   Stránky studií jsou mimochodem jediné, kde je „tisíce stránek" bezpečné — každá má unikátní peer-reviewed obsah a odkazuje na DOI.

2. **Šablona stránky entity** — pořadí sekcí je optimalizované pro extrakci LLM:
   - `<h1>` kanonický název + typ
   - **Summary** — 2–4 věty, faktické, bez marketingu (LLM citují první odstavec nejčastěji)
   - **Evidence at a glance** — tabulka počtu studií po tierech (A/B/C/D), ne hvězdičky
   - **Key studies** — 5–10 nejvýše hodnocených, každá s DOI odkazem
   - **Contradictions** — kde si studie odporují (viz Mechanism Explorer, 43 hran)
   - **Knowledge gaps** — z `atlas_gaps/`
   - **Related entities** — interní prolinkování
   - **FAQ** — jen tam, kde na otázku data skutečně odpovídají
   - **Provenance** — kdo kurátoroval, kdo revidoval, `dateModified`

3. **Per-page JSON-LD.** Ne jeden `Dataset` pro celý web jako dnes. Na stránce entity: `DefinedTerm` + `Dataset` + `FAQPage` (jen když FAQ existuje). Na stránce studie: `ScholarlyArticle` s `identifier` = DOI i PMID.

4. **SPA zůstává.** Neruší se — `/` dál servíruje interaktivní aplikaci. Statické stránky jsou vstupní body, které na SPA odkazují (`/gene/mtor` → tlačítko „Open in Atlas explorer"). Hybridní model, nulová regrese.

5. **Sitemap generátor** — z 1 URL na ~350. Rozdělit na `sitemap-entities.xml`, `sitemap-studies.xml` + index. `lastmod` z data revize, ne z data buildu (falešný lastmod si Google pamatuje).

6. **robots.txt** — explicitně povolit `GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `ClaudeBot`, `Google-Extended`, `CCBot`. Dnešní `Allow: /` funguje, ale explicitní záznam je dokumentace záměru a chrání před omylem v budoucnu.

7. **Kontrola kvality:** `curl -s URL | sed 's/<script.*<\/script>//' | wc -c` — musí vrátit >3000 znaků skutečného obsahu. Zaveďte jako test v `verify_index_html.py`.

**Odhad:** 1–2 dny. **Dopad: největší v celém plánu.**

---

### Fáze C — Citovatelnost (skutečná dlouhodobá výhoda)

Toto předběhne SEO. Vědec, který Atlas jednou odcituje, přinese víc než 1000 návštěv z Googlu.

1. **Zenodo DOI pro dataset.** Nahrajte `studies_baked.json` + `entities_baked.json` + `README` jako release. Zenodo přiděluje DOI přes DataCite → dataset se objeví v DataCite Commons, OpenAIRE a je strojově dohledatelný. Každý release = nová verze DOI, `concept DOI` odkazuje vždy na nejnovější. **Nejlevnější věc s nejvyšší návratností v celém dokumentu.**
2. **Licence.** CC BY 4.0 pro data, MIT pro kód. Bez explicitní licence vás nikdo institucionální nepoužije a AI crawlery mají důvod obsah vynechat.
3. **Statické API.** GitHub Pages umí servírovat JSON. Zdarma:
   ```
   /api/v1/studies.json
   /api/v1/entities.json
   /api/v1/entity/mtor.json
   /api/v1/relations.json
   ```
   Plus `/api/README` s příkladem v Pythonu a curl. Otevřené API je důvod, proč vás někdo zabuduje do vlastního nástroje — a tím vzniká zpětný odkaz, který nekoupíte.
4. **`CITATION.cff`** v rootu repa — GitHub z něj vyrobí tlačítko „Cite this repository".
5. **Verzování a changelog.** `/changelog` s datem, počtem studií a co přibylo. Citovatelný zdroj musí být reprodukovatelný: „Atlas v1.3, accessed 2026-07-27".
6. **`llms.txt`** v rootu — stručný strojově čitelný rozcestník. Adopce crawlery zatím **není potvrzená**, berte jako levnou sázku (15 min), ne jako pilíř.

---

### Fáze D — Obsah, ale jen kde na něj máte data

**Pravidlo kvality (quality gate).** Stránka se publikuje jen když splní:

- ≥ 3 studie navázané na entitu, **nebo** ≥ 1 studie tier A/B
- Summary říká něco, co není v abstraktu jedné studie (syntéza, ne parafráze)
- Prošla lidskou revizí (`reviewed_by` + `reviewed_on` vyplněné)

Co neprojde → **neexistuje jako URL.** Zůstane jako filtr uvnitř SPA. Tohle je jediná pojistka proti thin-content trestu.

Podle dnešních dat projde odhadem **40–70 stránek**. To je správný cíl pro rok jedna.

**Priorita psaní** (podle poměru objem hledanosti / dostupná data):
1. `/drug/rapamycin` — nejvíc dat i nejvíc poptávky
2. `/gene/mtor`, `/gene/tsc2`, `/gene/rheb`, `/gene/depdc5`
3. `/process/autophagy`
4. `/topic/mtor-and-aging`, `/topic/mtor-and-cancer` — landing pages podle nemocí, jak návrh správně navrhuje
5. `/question/does-rapamycin-extend-human-lifespan` — **ale jen otázky, kde Atlas má názor podložený daty a kde umí ukázat rozpor.** To je vaše diferenciace. Otázka, na kterou odpovíte stejně jako Wikipedie, nemá smysl.

**`/compare/*` odložte.** Smysluplné srovnání vyžaduje ≥5 studií na obou stranách. Dnes to splní možná 2 dvojice.

---

### Fáze E — Autorita a distribuce

1. **PMID backfill.** NCBI ID Converter API (`https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids=<doi>&format=json`), dávka po 200, ~10 minut práce. Doplní i PMCID → víte, které fulltexty jsou open access.
2. **Jmenný podpis.** Na každou stránku: kdo kurátoroval (Oliver, s odkazem na profil) a kdo revidoval. Anonymní web hodnotící lékařskou evidenci je v YMYL doméně strop, který neprorazíte obsahem.
3. **Odborný garant.** Návrh to zmiňuje a má pravdu — je to nejsilnější jednotlivá páka na důvěryhodnost. Konkrétně: oslovte 1–2 autory ze seznamu Top-5 authors, kteří už v Atlasu jsou. Nabídněte roli „scientific advisor" s viditelným jménem a právem veta na summary. Máte tabulku Events s 9 konferencemi — Praha je nejlevnější příležitost k osobnímu oslovení.
4. **Wikidata.** Založte položku pro Atlas, propojte přes `described at URL` na relevantní gene/drug položky. Wikidata je zdroj, ze kterého LLM čerpají nadprůměrně často.
5. **Seeding.** r/longevity, Longevity subreddit, Hacker News (Show HN), Lesswrong, biotwitter. Cíl nejsou návštěvy, ale to, aby se URL objevila v Common Crawl a v tréninkových/retrieval korpusech.

---

## 2. Doporučené pořadí a odhady

| Fáze | Úsilí | Dopad | Kdy |
|---|---|---|---|
| **B7** ověření renderu (měření) | 30 min | — | hned |
| **E1** PMID backfill | 30 min | střední | hned |
| **A** normalizace entit | 1 den (z toho 2–3 h ruční) | **blokující** | týden 1 |
| **B** statické pre-rendering + sitemap | 1–2 dny | **nejvyšší** | týden 1–2 |
| **C1–C4** Zenodo DOI, licence, API, CITATION | půl dne | **velmi vysoký** | týden 2 |
| **D** 10 nejlepších stránek s revizí | 2 týdny | vysoký | týden 3–4 |
| **E2–E3** autorství + garant | průběžně | **stropový** | od teď |
| **E4–E5** Wikidata, seeding | 1 den | střední | týden 5 |
| Next.js migrace | týdny | nízký **dnes** | až >2000 stránek |

---

## 3. Metriky, které sledovat (a které ne)

**Sledovat:**
- Počet indexovaných URL (GSC) — cílem je 350, ne 3000
- Zda AI asistenti Atlas citují: ručně se ptejte ChatGPT/Perplexity/Claude na „best evidence rapamycin lifespan human" jednou měsíčně a logujte
- Odkazy z `.edu` / `.org` domén
- Stažení Zenodo datasetu
- Volání `/api/v1/*` (přes Cloudflare, pokud předřadíte)

**Nesledovat:** celkovou návštěvnost. Pro tento projekt je 500 návštěv od vědců cennějších než 50 000 od náhodných čtenářů.

---

## 4. Jedna věta, která shrnuje rozdíl oproti původnímu návrhu

Původní návrh optimalizuje na **objem stránek**. Přepracovaný optimalizuje na **hustotu důkazů na stránku** a na **strojovou dostupnost obsahu** — protože Atlas nemá konkurenční výhodu v počtu URL, ale v tom, že jako jediný říká, kde si důkazy odporují a co se pořád neví.
