# Sjednocení typografie a UI podle Learn (Academy)

**Datum:** 2026-08-31 · **Stav:** plán, neimplementováno
**Zadání:** Learn má čitelnější běžné písmo, lepší nadpisy, vzdušnost. Přenést tenhle
styl na celý web.

---

## 1. Diagnóza — proč je Learn čitelnější

Není to náhoda ani lepší vkus jedné stránky. Learn běží na **jiné typografické
základně** než zbytek webu, protože statické stránky a SPA vznikly odděleně a nikdy
se nesladily.

| | SPA (`index.html`) | Statické str. + Learn (`build_pages.py`) |
|---|---|---|
| písmo textu | DM Sans | systémový stack (Segoe UI / SF / Roboto) |
| velikost | **14px** | **16px** |
| řádkování | **1.5** | **1.62** |
| šířka bloku | `.shell` 1440px | `.wrap` 760px (Learn 1060 / `.ac-main` 760) |
| dark mode | ano | **žádný** |

Learn navíc přidává vrstvu, kterou ostatní stránky nemají vůbec: eyebrow, `clamp()`
nadpis v hero, lede 17px/1.62, `.ac-idea p` 17px/1.62, `.ac-note`, sekce oddělené
34px, sticky rail. To je ten pocit „vzdušnosti".

### Rozdrobenost velikostí (změřeno)

| vrstva | deklarací `font-size` | různých hodnot | nejčastější |
|---|---|---|---|
| `index.html` | **270** | 32 | 11px (34×), 12px (32×), 10.5px (27×), 10px (22×) |
| `build_pages.py` shell | ~28 | 13 | 16px, 14px, 12px |
| `pathway/pathway.css` | **66** | 17 | 12.5px (10×), 10px (10×), 9.5px (9×) |

**Většina UI textu v Atlasu je pod 13px.** Existují hodnoty 8px, 8.5px, 9px, 9.5px,
10.5px, 11.5px, 12.5px, 13.5px, 14.5px, 15.5px — půlpixelové velikosti bez systému.
Žádný typografický scale neexistuje; každá komponenta si velikost vymyslela zvlášť.

---

## 2. Rozhodnutá východiska

- **Písmo textu:** systémový stack, jak ho má Learn. DM Sans zůstává na nadpisy,
  wordmark a čísla; IBM Plex Mono na chrome/labely; Cormorant Garamond jen tam, kde
  už je (intro headline, `.ac-q`).
- **Rozsah:** plný token systém, ne kosmetický pass.
- **Dark mode:** dotáhnout i na statické stránky v rámci téhle práce.

---

## 3. Cílový typografický systém

### 3.1 Škála

```css
:root{
  /* rodiny */
  --font-text: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --font-ui:   'DM Sans',var(--font-text);
  --font-mono: 'IBM Plex Mono',ui-monospace,monospace;
  --font-display:'Cormorant Garamond',Georgia,serif;

  /* velikosti — 8 stupňů místo 32 náhodných hodnot */
  --fs-micro:  11px;   /* JEN mono uppercase labely, eyebrow, badge */
  --fs-caption:13px;   /* meta řádky, popisky pod figurou, tabulkové hlavičky */
  --fs-small:  15px;   /* husté tabulky, sekundární UI */
  --fs-body:   16px;   /* výchozí text  ← klíčová změna proti dnešním 14px */
  --fs-lead:   17px;   /* lede, summary, klíčové odstavce */
  --fs-h3:     18px;
  --fs-h2:     21px;
  --fs-h1:     clamp(26px,3.4vw,34px);
  --fs-display:clamp(30px,4.2vw,42px);

  /* řádkování */
  --lh-tight:1.2;  --lh-snug:1.4;  --lh-body:1.62;  --lh-loose:1.7;

  /* měřítko řádku */
  --measure:68ch;        /* ~760px, jako .wrap a .ac-main */
  --measure-wide:1060px; /* Learn hub, dashboardy */

  /* vertikální rytmus */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:18px;
  --sp-5:26px; --sp-6:34px; --sp-7:48px;
}
```

### 3.2 Tvrdá pravidla

1. Žádný text pod `--fs-caption` (13px) **s výjimkou** mono uppercase labelů
   (`--fs-micro`), kde velká písmena a letter-spacing nesou čitelnost.
2. Žádné půlpixelové velikosti. Kdo dnes má 12.5px, dostane 13px nebo 15px.
3. Odstavcový text nikdy nepřesáhne `--measure`. Tabulky a mapa dráhy smí.
4. Nadpis nese hierarchii velikostí + váhy, ne barvou.
5. Řádkování se váže na velikost: displeje `--lh-tight`, UI `--lh-snug`, próza
   `--lh-body`.

---

## 4. Architektura — kde tokeny žijí

Dnes existují tři nezávislé CSS vrstvy bez sdíleného souboru:

```
index.html          3 × <style> blok, ~104 kB CSS   (SPA)
build_pages.py      shell() řádky 341–473            (~440 statických stránek)
pathway/pathway.css 409 řádků, lazy-loaded           (mapa dráhy)
```

**Návrh:** nový `assets/type.css` jako jediný zdroj pravdy pro typografii.

- Obsahuje **jen** typografii + rytmus + dark-theme paper/ink tokeny.
- **Nesahá na barvy evidence tierů** — ty zůstanou tam, kde jsou, protože je hlídá
  `check_tier_palette.py` (pravidlo 6: nepůjčovat tier proměnné napříč významy).
- `index.html` i `shell()` ho linkují: `<link rel="stylesheet" href="/assets/type.css?v=HASH">`.
- `pathway.css` tokeny dědí (načítá se do stejného dokumentu), jen přepíše svých 66
  hardcoded velikostí na `var(--fs-*)`.

**Cache-busting:** `pathway.css` se dnes stampuje přes `stamp_pathway_version.py`
(loader přidá `?v=<hash>`). `type.css` se ale načítá `<link>` při načtení stránky, ne
JS loaderem — potřebuje vlastní krok, který přepíše `href` v `index.html` **a** v
`shell()`. Bez toho uvidí vracející se návštěvník starý CSS na novém HTML.

---

## 5. Fáze

### Fáze 0 — baseline (0.5 h)
Playwright screenshoty všech ploch, light + dark, 1440px + 390px, do `_ui-baseline/`.
Bez nich nejde poznat regresi od záměru.

### Fáze 1 — tokeny bez vizuální změny (1–2 h) · **nízké riziko**
Vytvořit `assets/type.css`, kde tokeny **zrcadlí dnešní hodnoty**. Zalinkovat na obou
vrstvách. Nasadit. Web musí vypadat pixel za pixel stejně. Tím se ověří linkování,
cache-busting a deploy pipeline dřív, než se změní jediná velikost.

### Fáze 2 — statické stránky na úroveň Learn (2–3 h)
Přepsat `shell()` CSS na tokeny a zvednout ho tam, kde Learn už je: `--fs-lead` pro
`.summary` a `.abstract`, `--sp-6` mezi sekcemi, `h2` z 17px na `--fs-h2`, jednotné
`--measure`.

Jedním během `build_pages.py` se přegeneruje **~440 stránek**: 352 study, 47 author,
18 gene, 11 answers, 4 disease, 4 drug, 3 complex, glossary, browse, about, data.
Learn (`build_academy.py`) sdílí týž shell — po přepisu se z `ACADEMY_CSS` dá smazat
to, co bude platit globálně (`.ac-lede`, `.ac-idea p`, `.ac-note` → tokeny).

### Fáze 3 — SPA `index.html` (4–6 h) · **největší kus**
Nejdřív základ: `body{font:var(--fs-body)/var(--lh-body) var(--font-text)}`. Pak
komponenta po komponentě, ne mechanickým search-replace:

1. topbar, tabs, searchbar (chrome — smí zůstat drobný, mono)
2. Welcome / `.atlas-intro` (`.intro-lede` 14.5→`--fs-lead`, `.intro-section-desc`
   12.5→`--fs-body`, `.itl-body` 12→`--fs-small`)
3. Studies — **kandidát na kompromis**, viz §7
4. Authors, Open Questions, Timeline, Ask Atlas, About
5. `.hero-claim`, `.ipy-*` panely, chipy, statistiky

Zvlášť si vyžádá pozornost 22 výskytů 10px a 27 výskytů 10.5px — většina jsou mono
labely (→ `--fs-micro`), ale část je běžný text, který dnes nikdo nepřečte.

### Fáze 4 — `pathway.css` (2–3 h) · **nejcitlivější**
Popisky uvnitř SVG mají vazbu na geometrii uzlů; zvětšení textu může přetéct boxy.
Postup: nejdřív jen tokenizovat beze změny hodnot, pustit `pathway/smoke_test.js`
(2699 asercí), teprve pak zvedat po jednom stupni a po každém kroku znovu testovat.
Legenda a postranní panely (mimo SVG) se zvednou na `--fs-small` bez rizika.

### Fáze 5 — dark mode pro statické stránky (1–2 h)
Do `type.css` přidat `html[data-theme="dark"]` tokeny a do `shell()` tentýž
přepínač + inline skript, jaký má SPA (čte `localStorage['atlas-theme']` před
prvním paintem, jinak blikne). Kontrast znovu proměřit — statické stránky mají
vlastní `--soft:#55524C`, který v tmavém režimu neprojde.

### Fáze 6 — verifikace
- `check_tier_palette.py` — paleta tierů nedotčená
- `validate_pathway.py --strict`
- `node pathway/smoke_test.js` — 2699 asercí
- `verify_index_html.py`, `verify_academy.py`, `verify_prerender.py`
- `node prerender_tabs.js --check`
- Playwright: screenshot diff proti `_ui-baseline/`, light+dark × desktop+mobil
- kontrast: každá dvojice popředí/pozadí ≥ 4.5:1 (AA) v obou režimech
- ruční průchod na telefonu — `MOBILE_OPTIMISATION_2026-07-29.md` řešil, že 44px
  touch targety a card-tabulky nesmí zmizet

### Fáze 7 — deploy
`deploy_with_pathway_refresh.bat` (6 kroků včetně stamp a validace), ne holý
`deploy.bat` — protože se mění `pathway.css`.

---

## 6. Rizika a pasti

| riziko | opatření |
|---|---|
| `index.html` má 3.3 MB — Edit tool ořízne konec souboru | psát přes python + `fsync` + `verify_index_html.py`, jak už je zapsáno v paměti projektu |
| CRLF vs LF v OneDrive složce rozbije git reconcile | `reconcile_with_origin.py` je součástí `deploy.bat`, neobcházet |
| stará CSS z cache na novém HTML | cache-bust `type.css` v obou vrstvách, ověřit v inkognitu |
| SVG popisky v pathway přetečou | tokenizovat bez změny hodnot → test → teprve pak zvedat |
| 14→16px zvětší tabulku 352 studií o ~15 % výšky | v tabulkách držet `--fs-small`, viz §7 |
| 3 CSS vrstvy se znovu rozejdou | pravidlo do `AGENTS.md`: nová velikost písma jen jako `var(--fs-*)`; případně lint skript `check_type_tokens.py` po vzoru `check_tier_palette.py` |

---

## 7. Otevřená rozhodnutí (k odsouhlasení před Fází 3)

1. **Hustota tabulek.** Studies a Authors jsou skenovací plochy, ne próza. Návrh:
   `--fs-small` (15px) / `--lh-snug`, ne plných 16px. Chceš spíš čitelnost, nebo
   udržet počet řádků na obrazovku?
2. **Šířka `.shell` 1440px.** Návrh: nechat pro tabulky a mapu, ale prózu ve
   Welcome / About / Open Questions omezit na `--measure`. Dnes se řádky táhnou přes
   celou šířku, což je druhá půlka toho, proč se to hůř čte než Learn.
3. **Zůstane DM Sans na nadpisech?** Systémový stack pro text a DM Sans pro nadpisy
   je konzistentní pár. Alternativa je systémový stack všude a DM Sans jen ve
   wordmarku — čistší, ale značka ztratí kus charakteru.

---

## 8. Odhad

| fáze | čas |
|---|---|
| 0 baseline | 0.5 h |
| 1 tokeny | 1–2 h |
| 2 statické stránky | 2–3 h |
| 3 SPA | 4–6 h |
| 4 pathway | 2–3 h |
| 5 dark mode | 1–2 h |
| 6 verifikace | 1–2 h |
| **celkem** | **12–19 h**, rozumně ve 3 deploy dávkách (1+2 / 3 / 4+5) |

Každá dávka je samostatně nasaditelná a samostatně vratitelná.
