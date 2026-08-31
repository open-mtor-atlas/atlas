# Sjednocení typografie, chrome a layoutu podle Learn (Academy)

**Datum:** 2026-08-31 · **Stav:** plán, neimplementováno
**Zadání:** Learn má čitelnější běžné písmo, lepší nadpisy, vzdušnost. Přenést tenhle
styl na celý web. Rozšířeno o: sjednocení hlaviček/patiček/menu, drobečkové navigace
a zarovnání obsahu.

---

## 1. Diagnóza

### 1.1 Typografie — proč je Learn čitelnější

Není to vkus jedné stránky. Learn běží na **jiné typografické základně** než zbytek
webu, protože statické stránky a SPA vznikly odděleně a nikdy se nesladily.

| | SPA (`index.html`) | Statické str. + Learn (`build_pages.py`) |
|---|---|---|
| písmo textu | DM Sans | systémový stack (Segoe UI / SF / Roboto) |
| velikost | **14px** | **16px** |
| řádkování | **1.5** | **1.62** |
| dark mode | ano | **žádný** |

Learn navíc přidává vrstvu, kterou ostatní stránky nemají: eyebrow, `clamp()` nadpis
v hero, lede 17px/1.62, `.ac-idea p` 17px/1.62, `.ac-note`, sekce oddělené 34px,
sticky rail. To je ten pocit „vzdušnosti".

**Rozdrobenost velikostí (změřeno):**

| vrstva | deklarací `font-size` | různých hodnot | nejčastější |
|---|---|---|---|
| `index.html` | **270** | 32 | 11px (34×), 12px (32×), 10.5px (27×), 10px (22×) |
| `build_pages.py` shell | ~28 | 13 | 16px, 14px, 12px |
| `pathway/pathway.css` | **66** | 17 | 12.5px (10×), 10px (10×), 9.5px (9×) |

**Většina UI textu v Atlasu je pod 13px.** Existují 8px, 8.5px, 9px, 9.5px, 10.5px,
11.5px, 12.5px, 13.5px, 14.5px, 15.5px — půlpixelové velikosti bez systému.

### 1.2 Hlavičky, patičky, menu

Unifikace z 2026-08-30 (commit a5629b2) srovnala **wordmark a řádek tabů**. Zbytek
chrome sladěný není:

**Pravá strana hlavičky.** SPA má `.topbar-controls` — přepínač LEVEL
(Beginner/Student/Research) a MODE (Dark). Statické stránky mají tam, kde homepage má
tyhle ovládací prvky, **prázdno**: `grep -c "level-switch|toggleTheme|topbar-controls"
build_pages.py` = **0**. Hlavička statické stránky proto působí nedodělaně vedle
homepage, a Level je přitom site-wide stav v `localStorage`, který statické stránky
neumí ani přepnout, ani na něj zareagovat.

**Patičky se neshodují v ničem kromě horní linky a vycentrování:**

| | SPA `.site-footer` | Statické `footer.oma-footer` |
|---|---|---|
| obsah | jeden řádek | odstavec s popisem + řádek odkazů |
| písmo | mono 11px | mono 12px + systémový 13px v odstavci |
| odkazy | 2 (Browse, About) | **7** (Atlas, Browse, Academy, Answers, Glossary, About, Data) |
| „last updated" | ano | **ne** |

Návštěvník, který přejde z homepage na studii, dostane jinou patičku s jinou sadou
odkazů. To je navigační díra, ne jen kosmetika.

**Markup chrome žije na dvou místech** — ručně v `index.html` a v `shell()` v
`build_pages.py`. Proto se to rozešlo a proto to nav unification stálo 4 kola
oprav. Mechanismus na propojení ale už existuje: `build_pages.py` dnes injektuje do
patičky `index.html` odkaz na Browse mezi značky
`<!-- browse-link-added-by-build-pages -->` … `<!-- /browse-link -->`.

### 1.3 Drobečková navigace

Nejsou to dvě verze téhož — jsou to **dvě různé věci**:

| | SPA | Statické stránky |
|---|---|---|
| element | `.ase-eyebrow` uvnitř `.atlas-section-head` | `nav.crumb` (vlastní blok) |
| podoba | `OLIVER'S MTOR ATLAS · WELCOME` | `Oliver's mTOR Atlas › Academy` |
| písmo | IBM Plex Mono 11px, uppercase, letter-spacing .14em | systémový 13px, sentence case |
| odkazy | **žádné** (jen text) | ano, funkční |
| oddělení | žádné; linku dělá až `.atlas-section-head` pod titulkem | vlastní `border-bottom:2px solid` |
| JSON-LD | ne | `BreadcrumbList` |

SPA verze vypadá líp (drobná mono značka nad velkým titulkem, linka až pod celou
hlavicí sekce), ale je to slepá ulička — neodkazuje nikam. Statická verze je funkčně
správná, ale vizuálně těžší a rozbíjí rytmus vlastním rámečkem.

### 1.4 Zarovnání obsahu

Tohle je druhá polovina toho, proč se homepage čte hůř než Learn. **Šířka se na
homepage nastavuje u každého prvku zvlášť, ne kontejnerem.** Změřeno na Welcome:

```
.atlas-intro        — bez omezení → 1440px
.intro-headline     760px
.intro-lede         660px
.intro-section-desc 660px
.epistemic-note     — bez omezení → 1440px   ← na screenshotu přes celou obrazovku
.ipy-panel          660px
.ipy-other-grid     660px
.intro-stats        — bez omezení → 1440px
```

Čtyři různé šířky na jedné obrazovce a jeden blok přes celou plochu. V celém SPA je
**26 deklarací `max-width` v 15 různých hodnotách** (1560, 1440, 1100, 1000, 940, 900,
840, 820, 780, 760, 700, 660, 640, 600, 560px).

A proč obsah sedí v levé části obrazovky: `.shell` je široký 1440px a vycentrovaný,
ale text uvnitř má 660–760px a je zarovnaný doleva. Na 1400px monitoru je tedy shell
skoro přes celou šířku a obsah v něm visí u levého okraje s velkou prázdnou pravou
polovinou.

Learn to dělá správně: jeden `.wrap` (1060px, `margin:0 auto`) a uvnitř `.ac-main`
(760px). Šířku určuje kontejner, ne prvek — a kontejner je vycentrovaný. Jediné, co
Learn netrefuje, je hodnota: hlavička `.oma-topbar-inner` má 1100px, obsah 1060px,
takže levá hrana textu je o 20px vpravo od levé hrany wordmarku.

---

## 2. Rozhodnutá východiska

- **Písmo textu:** systémový stack, jak ho má Learn. DM Sans zůstává na nadpisy,
  wordmark a čísla; IBM Plex Mono na chrome/labely; Cormorant Garamond jen tam, kde
  už je (`.intro-headline`, `.ase-title`, `.ac-q`).
- **Rozsah:** plný token systém, ne kosmetický pass.
- **Dark mode:** dotáhnout i na statické stránky v rámci téhle práce.
- **Šířka stránky:** `--measure-wide` = **1100px**, aby obsah lícoval s hlavičkou.
- **Nadpisy:** DM Sans (`--font-ui`). Cormorant Garamond zůstává jen na velkých
  titulcích ploch, kde už je (`.intro-headline`, `.ase-title`, `.ac-q`).
- **Tabulky:** `--fs-small` (15px) / `--lh-snug` — čitelnost před hustotou, ale ne
  plných 16px.
- **Level switch na statických stránkách:** zobrazit **jen tam, kde skutečně něco
  dělá**, a tam plně funkční (bez navigace pryč). Jinde vůbec. Nahrazuje původní
  variantu (b) — viz §5.5.
- **Mapa dráhy zůstává plnošířková** (`.oma-bleed`) — viz §4.1.

Vše rozhodnuto 2026-08-31.

---

## 3. Typografický systém

### 3.1 Škála

```css
:root{
  /* rodiny */
  --font-text: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --font-ui:   'DM Sans',var(--font-text);
  --font-mono: 'IBM Plex Mono',ui-monospace,monospace;
  --font-display:'Cormorant Garamond',Georgia,serif;

  /* velikosti — 8 stupňů místo 32 náhodných hodnot */
  --fs-micro:  11px;   /* JEN mono uppercase labely, eyebrow, badge, drobečky */
  --fs-caption:13px;   /* meta řádky, popisky pod figurou, hlavičky tabulek */
  --fs-small:  15px;   /* husté tabulky, sekundární UI */
  --fs-body:   16px;   /* výchozí text  ← klíčová změna proti dnešním 14px */
  --fs-lead:   17px;   /* lede, summary, klíčové odstavce */
  --fs-h3:     18px;
  --fs-h2:     21px;
  --fs-h1:     clamp(26px,3.4vw,34px);
  --fs-display:clamp(30px,4.2vw,42px);

  /* řádkování */
  --lh-tight:1.2;  --lh-snug:1.4;  --lh-body:1.62;  --lh-loose:1.7;
}
```

### 3.2 Tvrdá pravidla

1. Žádný text pod `--fs-caption` (13px) **s výjimkou** mono uppercase labelů
   (`--fs-micro`), kde velká písmena a letter-spacing nesou čitelnost.
2. Žádné půlpixelové velikosti. Kdo má dnes 12.5px, dostane 13px nebo 15px.
3. Řádkování se váže na velikost: displeje `--lh-tight`, UI `--lh-snug`, próza
   `--lh-body`.
4. Nadpis nese hierarchii velikostí a váhou, ne barvou.
5. Nadpisy jdou v `--font-ui` (DM Sans). Výjimka jsou velké titulky ploch, kde už dnes
   běží Cormorant Garamond (`.intro-headline`, `.ase-title`, `.ac-q`) — ty zůstávají,
   protože nesou redakční charakter značky.

---

## 4. Layoutový systém

Šířka přestává být vlastností prvku a stává se vlastností kontejneru — přesně jak to
dělá Learn.

```css
:root{
  --measure:68ch;         /* ~760px — odstavcový text, jako .ac-main */
  --measure-wide:1100px;  /* stránkový kontejner — lícuje s .oma-topbar-inner */
  --frame:1440px;         /* vnější rám, jen pro plnošířkové plochy */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:18px;
  --sp-5:26px; --sp-6:34px; --sp-7:48px;
}
.oma-page {max-width:var(--measure-wide); margin:0 auto;}  /* výchozí */
.oma-prose{max-width:var(--measure);}                      /* odstavce uvnitř */
.oma-bleed{max-width:var(--frame); margin:0 auto;}         /* výjimka, vědomá */
```

**Pravidla:**

1. Každá plocha sedí v `.oma-page` a je **vycentrovaná** — tím zmizí prázdná pravá
   polovina obrazovky. Šířka 1100px je zvolená tak, aby lícovala s dnešním
   `.oma-topbar-inner` (1100px): wordmark, taby i text sedí na téže svislici a
   stránka má jednu levou hranu odshora dolů. Learn se tím z 1060px o 40px rozšíří.
2. Odstavcový text nikdy nepřesáhne `--measure`.
3. `.oma-bleed` (1440px) dostanou jen tři plochy, kde to má smysl: mapa dráhy,
   tabulka Studies a tier matice. Nikde jinde. U mapy to není preference, ale
   nutnost — viz §4.1.
4. Z komponent se **odstraní všech 26 individuálních `max-width`**. `.epistemic-note`
   a spol. přestanou být plnošířkové tím, že zdědí kontejner.

### 4.1 Vejde se mapa dráhy do 1100px? Ne — a proto zůstane plnošířková

Mapa není obrázek pevné velikosti, je to kamera nad plátnem **1600 × 1464** jednotek
(`model.json` → `meta.canvas`), 88 uzlů, 119 interakcí. SVG má
`preserveAspectRatio="xMidYMid meet"` a `.pw-canvas svg{width:100%;height:100%}`, takže
se do kontejneru vždycky „vejde" — otázka není jestli, ale **v jakém měřítku**.

Vedle plátna sedí inspektor: `.pw-stage{grid-template-columns:minmax(0,1fr) 330px;
gap:16px}`. Spočítáno s dnešním `.shell` paddingem 26px:

| šířka stránky | dostupné | − rail 330 − gap 16 | **plátno** | měřítko modelu |
|---|---|---|---|---|
| 1440px (dnes) | 1388 | | **1042px** | ~0.76 |
| 1100px | 1048 | | **702px** | ~0.51 |

Plátno by se zúžilo o **třetinu**. Protože kamera do něj mapuje 1376+ jednotek modelu
(`pathway.js` ř. 458 drží podlahu `canvas.w * 0.86`), zmenší se všechno včetně popisků:
`.pw-n text` má 11.5px, což dnes při fit-all vychází na ~8.7 skutečných pixelů a při
1100px by to bylo **~5.9px**. Nečitelné.

**Závěr:** `#mapView` dostane `.oma-bleed` a zůstane na `--frame` (1440px). Je to
vědomá výjimka ze tří v §4 — mapa, tabulka Studies a tier matice — ne nedůslednost.
Sekce **kolem** mapy (lede, popisky režimů, legenda, kroky trasy) do `.oma-page`
patří; ty se dnes taky roztahují a číst se mají jako text.

### 4.2 Responsivita

Zastropování na 1100px mění chování **jen nad 1100px** — pod tím byl layout fluidní
už dneska a zůstává. Konkrétně u mapy:

- `@media (max-width:900px)` už dnes sklápí `.pw-stage` do jednoho sloupce a mění
  inspektor na spodní sheet (`position:fixed`, `max-height:62vh`). Tenhle breakpoint
  se nesmí posunout.
- Mezi 900 a 1100px je stávající úzké místo: při 950px viewportu má plátno 552px.
  1100px cap to nezhoršuje, ale při verifikaci se to musí projít.
- `.pw-canvas{height:min(72vh,760px)}` → pod 900px `58vh`. Beze změny.
- Statické stránky mají vlastní breakpointy na 760/560/380px
  (`MOBILE_OPTIMISATION_2026-07-29.md`: 44px touch targety, tabulky jako karty).
  `--measure-wide` je `max-width`, ne `width`, takže je nechává být.

Kontrolní pravidlo: **žádný nový breakpoint.** Token je strop, ne rozvržení.

---

## 5. Chrome: hlavička, patička, drobečky

### 5.1 Jeden zdroj markupu

Chrome se přestane psát dvakrát. `build_pages.py` dostane konstanty `TOPBAR_HTML`,
`FOOTER_HTML`, `CRUMB_HTML` a bude je injektovat i do `index.html` mezi značkové
komentáře — **stejným mechanismem, jaký už funguje** pro
`<!-- browse-link-added-by-build-pages -->`. Deploy tím dostane záruku, že se hlavička
a patička nemůžou rozejít, protože obě vrstvy čtou týž řetězec.

### 5.2 Hlavička

Statické stránky dostanou `.topbar-controls` s ovládacími prvky z homepage:

- **MODE (dark/light)** — plnohodnotně, včetně inline skriptu, který čte
  `localStorage['atlas-theme']` **před prvním paintem** (jinak stránka blikne bíle).
- **LEVEL (Beginner/Student/Research)** — podmíněně, podle typu stránky. Kde se
  zobrazí, tam skutečně přepíná obsah na místě; kde by nic nedělal, tam se
  nevykreslí. Rozpis v §5.5.

### 5.3 Patička

Jedna patička pro celý web, složená z toho lepšího z obou:

```
[odstavec s popisem projektu]        systémový font, --fs-caption, max-width:--measure
[7 odkazů: Atlas · Browse · Academy · Answers · Glossary · About · Data]
[Oliver's mTOR Atlas · last updated <čas> · 458 pages]   mono, --fs-micro
```

Řádek „last updated" je dnes jen v SPA, přitom u statických stránek je informačně
cennější (crawler i čtenář vidí, jak čerstvý obsah je). Sedmiodkazový řádek je dnes
jen na statických stránkách, přitom z homepage se na Academy/Answers/Glossary přes
patičku vůbec nedostaneš.

### 5.4 Drobečková navigace

Vzít **vizuální podobu z homepage** a **funkčnost ze statických stránek**:

```html
<nav class="oma-crumb" aria-label="Breadcrumb">
  <a href="/">Oliver's mTOR Atlas</a> · <b>Academy</b>
</nav>
```

```css
.oma-crumb{font-family:var(--font-mono);font-size:var(--fs-micro);
  letter-spacing:.14em;text-transform:uppercase;color:var(--ink-soft);
  margin:0 0 var(--sp-3);border:0}          /* žádný vlastní border-bottom */
.oma-crumb a{color:inherit;text-decoration:none}
.oma-crumb a:hover{color:var(--teal)}
.oma-crumb b{color:var(--teal);font-weight:600}
```

Změny proti dnešku:

- **Na homepage:** segmenty se stanou odkazy (dnes je to jen text). Pozice, mono
  písmo i letter-spacing zůstávají — vypadat to bude stejně.
- **Na statických stránkách:** z 13px sentence-case bez uppercase se stane táž mono
  značka; **zmizí vlastní `border-bottom:2px solid`** a oddělovací linku převezme
  hlavice sekce pod titulkem, jako na homepage. `›` se sjednotí na `·`.
- `BreadcrumbList` JSON-LD na statických stránkách **zůstává** a nově se přidá i na
  homepage, když už tam budou odkazy.

### 5.5 Level switch jen tam, kde něco dělá

Původní varianta (b) — přepínač všude, klik odveze na SPA — je zbytečný kompromis.
Průzkum dat ukázal, že **podklady pro skutečné přepínání na místě už z velké části
existují**, jen je `build_pages.py` nepoužívá.

| typ stránky | ks | co pro úrovně existuje | verdikt |
|---|---|---|---|
| **entity** (gene, complex, disease, drug, condition, intervention) | 31 | `model.json` má `explain.beginner` / `student` / `research` pro **všech 88 uzlů**; 21 z 31 stránek se trefí na uzel přímo, zbytek po doplnění slug mapy (`akt-pkb`→`AKT`, `tsc1-tsc2`→`TSC1/2`…) | **plný přepínač** — text existuje, nic se nedopisuje |
| **question** (gaps) | 10 | stránka dnes renderuje `basis_beginner` **i** `basis` pod sebou (ř. 767–775), stejně `hyp_beginner`/`hyp` | **plný přepínač** — vybere jednu verzi místo obou, stránka se navíc zkrátí |
| **study** | 352 | textové varianty nejsou (pole: `title`, `finding`, `abstract`, `ai_*`, `tier`, `doi`, `pmid`) | **přepínač jako disclosure** — Beginner skryje abstrakt a AI-extrahovaná technická pole, Research je otevře rovnou. Přesně to, co SPA dnes dělá v Studies |
| **answers** | 11 | ručně psané, jednoúrovňové | skrýt |
| **glossary**, **author**, **about**, **data**, **browse** | 51 | ručně psané / meta | skrýt |
| **Academy** (lekce) | 10+ | psané záměrně pro jednu didaktickou úroveň, s vlastní progresí a kvízy | **skrýt — a to je věcné rozhodnutí, ne úspora práce.** Přepínač úrovní by popřel to, čím Academy je |

**Důsledek:** varianta (b) padá. Přepínač buď funguje na místě (entity, question,
study = **393 stránek**), nebo tam vůbec není (65 stránek). Nikde nebude ovládací
prvek, který ve skutečnosti odnaviguje pryč — čímž mizí i UX dluh z §9.

**Co to stojí navíc:**

1. `build_pages.py` začne číst `pathway/model.json` (dnes ho nečte vůbec) a zapéct do
   entity stránek všechny tři varianty textu. Nová závislost mezi buildem stránek
   a pathway modelem — `deploy_with_pathway_refresh.bat` už oba kroky pouští ve
   správném pořadí (model → stránky), takže stačí ohlídat, že se `build_pages.py`
   nepustí proti zastaralému modelu.
2. Malý sdílený skript v `shell()`: přečte `localStorage['atlas-level']`, přepne
   `data-level` na `<html>`, zbytek obstará CSS (`[data-level="beginner"] .lv-research
   {display:none}`). **Bez JS zůstane viditelná úroveň Student** — crawler i čtenář
   bez skriptu tak dostanou plnohodnotnou stránku.
3. `shell()` dostane parametr `level_switch=True|False`, aby volající stránka
   rozhodla. Výchozí `False` — přepínač se objeví jen tam, kde se o něj někdo přihlásí.

**Pozor na SEO:** všechny tři varianty budou v HTML a dvě z nich skryté přes CSS.
To je legitimní (progresivní zpřístupnění téhož obsahu, ne cloaking — nejde o jiný
text pro robota než pro člověka), ale je potřeba: nechat `student` variantu viditelnou
bez JS, nepoužívat `hidden`/`aria-hidden` na text, který má být indexovatelný,
a v `<meta description>` a JSON-LD dál používat `student` verzi jako dnes.

---

## 6. Architektura CSS

Dnes existují tři nezávislé vrstvy bez sdíleného souboru:

```
index.html          3 × <style> blok, ~104 kB CSS   (SPA)
build_pages.py      shell() řádky 341–473            (~440 statických stránek)
pathway/pathway.css 409 řádků, lazy-loaded           (mapa dráhy)
```

**Návrh:** nový `assets/type.css` jako jediný zdroj pravdy pro typografii a layout.

- Obsahuje **jen** typografii, layout tokeny, chrome a dark-theme paper/ink.
- **Nesahá na barvy evidence tierů** — hlídá je `check_tier_palette.py` (pravidlo 6:
  nepůjčovat tier proměnné napříč významy).
- `index.html` i `shell()` ho linkují: `<link rel="stylesheet" href="/assets/type.css?v=HASH">`.
- `pathway.css` tokeny dědí (načítá se do téhož dokumentu), jen přepíše svých 66
  hardcoded velikostí na `var(--fs-*)`.

**Cache-busting:** `pathway.css` se dnes stampuje přes `stamp_pathway_version.py`
(loader přidá `?v=<hash>`). `type.css` se ale načítá `<link>` při načtení stránky, ne
JS loaderem — potřebuje vlastní krok, který přepíše `href` v `index.html` **a** v
`shell()`. Bez toho uvidí vracející se návštěvník starý CSS na novém HTML.

---

## 7. Fáze

### Fáze 0 — baseline (0.5 h)
Playwright screenshoty všech ploch, light + dark, 1440px + 390px, do `_ui-baseline/`.
Bez nich nejde poznat regresi od záměru.

### Fáze 1 — tokeny bez vizuální změny (1–2 h) · **nízké riziko**
Vytvořit `assets/type.css`, kde tokeny **zrcadlí dnešní hodnoty**. Zalinkovat na obou
vrstvách. Nasadit. Web musí vypadat pixel za pixel stejně. Ověří se tím linkování,
cache-busting a deploy pipeline dřív, než se změní jediná velikost.

### Fáze 2 — chrome do jednoho zdroje (2–3 h)
`TOPBAR_HTML` / `FOOTER_HTML` / `CRUMB_HTML` v `build_pages.py`, injektáž do
`index.html` mezi značky, sjednocená patička (§5.3), `.topbar-controls` a přepínač
tématu na statické stránky (§5.2). **Zatím beze změny typografie** — jen se srovná
struktura, aby se pak měnila na jednom místě.

### Fáze 2b — level switch podle typu stránky (3–4 h)
Podle §5.5: `shell(level_switch=...)`, sdílený skript `data-level` na `<html>`,
`build_pages.py` začne číst `model.json` a zapéct tři varianty do entity stránek,
question stránky přestanou zobrazovat obě verze pod sebou, study stránky dostanou
disclosure. Ověřit **bez JS**: viditelná musí zůstat úroveň Student a stránka musí
dávat plný smysl.

### Fáze 3 — statické stránky na úroveň Learn (2–3 h)
Přepsat `shell()` CSS na tokeny a zvednout ho tam, kde Learn už je: `--fs-lead` pro
`.summary` a `.abstract`, `--sp-6` mezi sekcemi, `h2` na `--fs-h2`, `.oma-page` /
`.oma-prose` místo `.wrap`, nové drobečky (§5.4).

Jedním během `build_pages.py` se přegeneruje **~440 stránek**: 352 study, 47 author,
18 gene, 11 answers, 4 disease, 4 drug, 3 complex, glossary, browse, about, data.
Learn (`build_academy.py`) sdílí týž shell — po přepisu se z `ACADEMY_CSS` smaže to,
co bude platit globálně (`.ac-lede`, `.ac-idea p`, `.ac-note` → tokeny), **včetně
jeho vlastních přepisů `.wrap{max-width:1060px}` a `nav.crumb{max-width:1060px}`** —
ty ustoupí `--measure-wide` (1100px). Learn se tím o 40px rozšíří; zkontrolovat na
screenshot diffu, že se `.ac-lesson` grid (`1fr 230px`, gap 44px) a sticky rail
nerozsypou.

### Fáze 4 — SPA `index.html` (5–7 h) · **největší kus**
Nejdřív základ: `body{font:var(--fs-body)/var(--lh-body) var(--font-text)}` a zabalení
každé plochy do `.oma-page`. Pak komponenta po komponentě, ne search-replace:

1. topbar, tabs, searchbar (chrome — smí zůstat drobný, mono)
2. Welcome / `.atlas-intro` — **odstranit všech 8 individuálních šířek** (§1.4),
   `.intro-lede` 14.5→`--fs-lead`, `.intro-section-desc` 12.5→`--fs-body`,
   `.itl-body` 12→`--fs-small`, `.epistemic-note` 12.5→`--fs-small` a do kontejneru
3. Studies a Authors — `--fs-small` (15px) / `--lh-snug`, ne `--fs-body` (§2)
4. Authors, Open Questions, Timeline, Ask Atlas, About
5. `.hero-claim`, `.ipy-*` panely, chipy, statistiky

Zvlášť si vyžádá pozornost 22 výskytů 10px a 27 výskytů 10.5px — většina jsou mono
labely (→ `--fs-micro`), ale část je běžný text, který dnes nikdo nepřečte.

### Fáze 5 — `pathway.css` (2–3 h) · **nejcitlivější**
Popisky uvnitř SVG mají vazbu na geometrii uzlů; zvětšení textu může přetéct boxy.
Postup: nejdřív jen tokenizovat beze změny hodnot, pustit `pathway/smoke_test.js`
(2699 asercí), teprve pak zvedat po jednom stupni a po každém kroku znovu testovat.
Legenda a postranní panely (mimo SVG) se zvednou na `--fs-small` bez rizika.

Zvlášť v téhle fázi: `#mapView` dostane `.oma-bleed` (§4.1) a **ověří se, že plátno na
1440px viewportu má pořád ~1042px**, ne 702. Responsivita podle §4.2: breakpoint 900px
se nesmí hnout, žádný nový nepřibude.

### Fáze 6 — dark mode pro statické stránky (1–2 h)
Do `type.css` přidat `html[data-theme="dark"]` tokeny; přepínač už na stránkách bude
z fáze 2. Kontrast znovu proměřit — statické stránky mají vlastní `--soft:#55524C`,
který v tmavém režimu neprojde.

### Fáze 7 — verifikace
- `check_tier_palette.py` — paleta tierů nedotčená
- `validate_pathway.py --strict`
- `node pathway/smoke_test.js` — 2699 asercí
- `verify_index_html.py`, `verify_academy.py`, `verify_prerender.py`
- `node prerender_tabs.js --check` — prerendrované taby nesou `.ase-eyebrow` markup,
  po změně drobečků se **musí přegenerovat**
- Playwright: screenshot diff proti `_ui-baseline/`, light+dark × **1440 / 1200 /
  1100 / 950 / 900 / 760 / 560 / 390px** — 950 a 900 jsou ta úzká místa u mapy,
  1100 a 1200 ověří, že cap nikde neuřízne plnošířkové plochy
- šířka `.pw-canvas` na 1440px viewportu ≥ 1000px (jinak mapě spadl `.oma-bleed`)
- kontrola, že hlavička i patička jsou byte-identické mezi `/` a `/study/<id>/`
- kontrast: každá dvojice popředí/pozadí ≥ 4.5:1 (AA) v obou režimech
- ruční průchod na telefonu — `MOBILE_OPTIMISATION_2026-07-29.md` řešil 44px touch
  targety a card-tabulky, nesmí zmizet

### Fáze 8 — deploy
`deploy_with_pathway_refresh.bat` (6 kroků včetně stamp a validace), ne holý
`deploy.bat` — protože se mění `pathway.css`.

---

## 8. Rozhodnuto

Všechny otevřené body z první verze plánu jsou uzavřené (2026-08-31) — viz §2.
Shrnutí i s důsledky:

| rozhodnutí | důsledek pro implementaci |
|---|---|
| šířka 1100px | `ACADEMY_CSS` ztrácí přepisy `.wrap`/`nav.crumb{1060px}`; Learn se o 40px rozšíří |
| mapa dráhy plnošířková | `#mapView` = `.oma-bleed` (§4.1); okolní text ale do `.oma-page` |
| tabulky 15px | `--fs-small`/`--lh-snug` pro Studies a Authors, ne `--fs-body` |
| DM Sans na nadpisech | `h1–h4` = `--font-ui`; Cormorant jen `.intro-headline`, `.ase-title`, `.ac-q` |
| level switch podmíněně | plný přepínač na entity/question/study (393 str.), skrytý jinde (65 str.) a záměrně i v Academy; `build_pages.py` začne číst `model.json` (§5.5) |

## 9. Rizika a pasti

| riziko | opatření |
|---|---|
| `index.html` má 3.3 MB — Edit tool ořízne konec souboru | psát přes python + `fsync` + `verify_index_html.py`, jak už je v paměti projektu |
| injektáž chrome do `index.html` může rozbít 3.3MB soubor | psát jen mezi značkové komentáře, po zápisu vždy `verify_index_html.py` |
| prerendrované taby nesou starý markup drobečků | `prerender_tabs.js` pustit po fázi 4, `--check` v CI gate |
| CRLF vs LF v OneDrive složce rozbije git reconcile | `reconcile_with_origin.py` je součástí `deploy.bat`, neobcházet |
| stará CSS z cache na novém HTML | cache-bust `type.css` v obou vrstvách, ověřit v inkognitu |
| SVG popisky v pathway přetečou | tokenizovat bez změny hodnot → test → teprve pak zvedat |
| 14→16px zvětší tabulku 352 studií o ~15 % výšky | v tabulkách držet `--fs-small` (15px), rozhodnuto v §2 |
| odebrání `max-width` u komponent je rozbije | jde o 26 deklarací; po jedné, se screenshot diffem |
| přepínač úrovní chybí na části stránek → působí, že hlavička „bliká" mezi typy stránek | prázdné místo si drží šířku (`visibility:hidden`, ne `display:none`), aby MODE nepřeskakoval; ověřit na průchodu study → author → glossary |
| entity stránky se postaví proti zastaralému `model.json` | `deploy_with_pathway_refresh.bat` pouští model před stránkami; přidat do `build_pages.py` kontrolu `meta.generated` a varování, když je model starší než poslední změna kurace |
| tři varianty textu v HTML → riziko, že se skryté indexuje jako duplicita | `student` varianta viditelná bez JS, žádné `aria-hidden` na indexovatelný text, `<meta description>` a JSON-LD dál ze `student` (§5.5) |
| rozšíření Learn na 1100px rozhodí `.ac-lesson` grid (`1fr 230px`, gap 44px) a sticky rail | screenshot diff lekce na 1100 / 900 / 390px |
| 1100px cap zúží plochu mapy, pokud se `.oma-bleed` zapomene | smoke test kontroluje šířku `.pw-canvas` > 1000px na 1440px viewportu |
| 3 CSS vrstvy se znovu rozejdou | pravidlo do `AGENTS.md`: velikost jen `var(--fs-*)`, šířka jen kontejnerem; případně lint `check_type_tokens.py` po vzoru `check_tier_palette.py` |

---

## 10. Odhad

| fáze | čas |
|---|---|
| 0 baseline + CWV/PSI měření | 1 h |
| 1 tokeny | 1–2 h |
| 2 chrome do jednoho zdroje | 2–3 h |
| 2b level switch podle typu stránky (§5.5) | 3–4 h |
| 3 statické stránky | 2–3 h |
| 4 SPA | 5–7 h |
| 5 pathway | 2–3 h |
| 6 dark mode | 1–2 h |
| 7 verifikace + SEO kontroly | 2–3 h |
| **celkem** | **19–28 h** |

**Nasaditelné dávky:** (1+2) chrome bez vizuální změny · (3+6) statické stránky
včetně dark mode · (4) SPA · (5) pathway. Každá samostatně vratitelná.

---

## 11. SEO a GEO

Web má podle auditu z 2026-08-23 **nula externích zpětných odkazů** a 255 stránek ve
stavu „objeveno, neindexováno". Za těch okolností je interní prolinkování, strukturovaná
data a rychlost prakticky jediné, co se dá ovlivnit — takže tenhle refaktor se jich
nesmí ani dotknout k horšímu.

### 11.1 Co se nesmí rozbít

| plocha | dnešní stav | pravidlo pro refaktor |
|---|---|---|
| `BreadcrumbList` JSON-LD | **352×** na study stránkách + na entity/question, navázaný na viditelnou `nav.crumb` | Google chce, aby se schéma shodovalo s **viditelným** textem. Velká písmena dělat **výhradně přes CSS `text-transform`**, nikdy je nepsat do markupu — DOM tak dál nese „Oliver's mTOR Atlas" a JSON-LD zůstává platné. Odkazy (`href`) v drobečku musí zůstat. |
| interní odkazy v patičce | statické stránky **7**, homepage **2** | Sjednocená patička má mít **≥ 7 odkazů na každé stránce**. Nikdy nesnižovat — homepage jich 5 získá. |
| `canonical` + `<meta robots>` | self-referenční na každé generované stránce | Injektáž chrome sahá jen mezi značkové komentáře v `<body>`; `<head>` blok v `shell()` zůstává netknutý. |
| `ScholarlyArticle` 352×, `Person` 1400×, `PropertyValue` (DOI/PMID) 660×, `FAQPage`, `DefinedTerm`, `CollectionPage`, `Dataset` | platné, GSC bez chyb | Měníme CSS a chrome, ne datové bloky. Ověřit po fázi 3 a 4 Rich Results Testem. |
| nadpisová osnova | h1 → h2 → h3 | Typografie mění **velikost, ne tag**. Nikdy neměnit úroveň nadpisu kvůli vzhledu. |
| `llms.txt`, `robots.txt`, sitemapy | generované, robots explicitně pouští GPTBot/ClaudeBot/PerplexityBot | Beze změny; po přegenerování ověřit, že `llms.txt` odkazuje na tytéž URL. |
| redirect stuby (`LEGACY_SLUGS`) | dnes prázdné `{}`, ale procházejí `shell()` | Až se naplní, ověřit, že injektáž chrome nerozbije canonical ani meta refresh. |

### 11.2 Co se tím naopak zlepší (a proto to stojí za změření)

- **Váha stránky −37 %.** Ve study stránce je dnes **6 857 B inline CSS z 18 305 B**, tedy
  **37 % každé stránky je duplikované CSS**. Napříč 458 stránkami se pořád dokola servíruje
  ~3,1 MB téhož. Jeden cachovaný `assets/type.css` to smaže — přímý zisk pro crawl budget
  i pro reálné návštěvníky.
- **Fonty na homepage jsou dnes zapojené nejhorším možným způsobem.** `index.html` je
  načítá `@import url(...)` **uvnitř `<style>` bloku a bez jediného `preconnect`** —
  prohlížeč musí nejdřív stáhnout a rozparsovat CSS, než vůbec zjistí, že má sáhnout pro
  font. Statické stránky to přitom dělají správně (`preconnect` + `<link>`). Sjednocení
  chrome tenhle rozdíl smaže a je to zisk zadarmo.
- **Míň souborů s fonty.** Homepage si dnes říká o **11 řezů** (Cormorant 5 + DM Sans 3 +
  IBM Plex Mono 3). Když běžný text přejde na systémový stack, DM Sans zbude na nadpisy a
  wordmark → část řezů se dá vypustit.
- **„Text too small to read".** 14 → 16px je přímo ta metrika, kterou Google hlídá
  v mobilní použitelnosti.
- **Homepage získá `BreadcrumbList`.** Dnes má jen `Person`, `Organization`, `Dataset`
  a `DataDownload` — drobečky tam sice vypadají jako drobečky, ale jsou to jen text bez
  odkazů, takže schéma chybí právem. Jakmile podle §5.4 dostanou odkazy, dává smysl
  schéma doplnit.

### 11.3 Rizika, která přináší právě tenhle refaktor

| riziko | ošetření |
|---|---|
| externí `type.css` je render-blocking → horší FCP/LCP než dnešní inline | rozhodnout podle **CWV baseline z fáze 0**: buď kritické CSS (topbar + první obrazovka) nechat inline v `shell()` a zbytek linkovat, nebo přijmout jeden request navíc, protože se ušetří 37 % váhy stránky. Neřešit od stolu — změřit. |
| tři varianty textu, dvě skryté CSS → čtení jako duplicita nebo keyword stuffing | **`student` je kanonická verze**: viditelná bez JS, ta se indexuje, z ní jde `<meta description>` i JSON-LD. `beginner`/`research` jsou progresivní vylepšení, ne druhá jazyková mutace — a nepočítat s tím, že se zaindexují. Není to cloaking: robot i člověk dostanou totéž. |
| viditelný drobeček se rozejde s `BreadcrumbList` | kontrola přímo v `build_pages.py`: text viditelného drobečku se musí rovnat `name` v JSON-LD, jinak build spadne (stejná logika jako `check_tier_palette.py`) |
| přegenerování 440 stránek rozhýbe `lastmod` v sitemapách a spotřebuje crawl budget, zatímco 255 stránek čeká na první návštěvu | statické stránky přegenerovat **v jednom deploy**, ne ve dvou — proto jsou fáze 3 a 6 v jedné dávce. A nedělat to uprostřed sledování indexace v GSC. IndexNow ping už v `deploy.bat` je. |
| změna typografie svede ke změně tagu nadpisu | pravidlo z §11.1 do `AGENTS.md` |

### 11.4 Co to přidává do fází

- **Fáze 0** navíc: **PageSpeed Insights baseline** na `/` a na jedné `/study/…` stránce.
  Audit z 2026-08-23 uvádí Core Web Vitals jako „nikdy neměřeno" — bez baseline nepůjde
  po refaktoru odlišit zlepšení od zhoršení a rozhodnout otázku inline vs. externí CSS.
- **Fáze 7** navíc: znovu PSI a porovnat; Rich Results Test na jedné stránce od každého
  typu (study, entity, question, answer, glossary, browse, homepage); automatická kontrola
  „viditelný drobeček == JSON-LD"; kontrola, že patička má všude ≥ 7 odkazů.

---

## 12. Navazující práce (mimo tenhle plán)

1. **Dopsat `explain` k interakcím.** `model.json` má tři úrovně u všech 88 uzlů, ale
   u **0 ze 119 interakcí**. Až budou, může se úrovňový text dostat i do popisů vazeb
   na entity stránkách a do Mechanism Exploreru.
2. **Lint `check_type_tokens.py`** — zakáže nový `font-size:<px>` a `max-width:<px>`
   mimo `type.css`, po vzoru `check_tier_palette.py`. Bez něj se vrstvy zase rozejdou.
3. **Dark mode pro `pathway.css`** — dnes tokeny dědí, ale kontrast uzlů a hran
   v tmavém režimu nikdo neproměřil.
