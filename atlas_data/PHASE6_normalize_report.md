# Fáze 6, krok 2 — normalizace entit

Vygenerováno: 2026-07-27 13:26 · 276 studií

## Kolik práce zbývá na člověka

| | počet |
|---|---|
| Unikátních atomů po rozbití | 325 |
| **K rozhodnutí (>= 3 studií)** | **41** |
| Odloženo (pod prahem) | 284 |
| Zamítnuto jako 'není entita' | 8 unikátních |

Rozhoduje se jen o horní skupině. Položka pod prahem nemůže projít
quality gate, takže na ni nemá smysl utrácet pozornost teď.

## Návrhy hran pro tabulku Relations

Z pořadí atomů v AI_Target (`A / B / C` = směr signálu) vzniklo
**230 unikátních dvojic** z 306 výskytů. Všechny jsou `Proposed` a
`heuristic-order` — pořadí ve volném textu NENÍ důkaz směru regulace,
je to jen kandidát pro tvůj existující review workflow.

## Nejčastější atomy

| # | atom | zmínek | studií | varianty |
|---|---|---|---|---|
| 1 | mTORC1 | 134 | 120 | mTORC1; mTORC1 activation; mTORC1 amino-acid sensors |
| 2 | mTOR | 107 | 97 | MTOR; mTOR; mTOR activity |
| 3 | mTORC2 | 40 | 35 | mTORC2; mTORC2 core |
| 4 | Rapamycin | 37 | 37 | Rapamycin; rapamycin |
| 5 | Akt | 20 | 17 | AKT; Akt |
| 6 | Rheb | 14 | 11 | RHEB; Rheb |
| 7 | AMPK | 14 | 11 | AMPK |
| 8 | Rag GTPases | 13 | 11 | Rag GTPases |
| 9 | TSC2 | 12 | 9 | TSC2 |
| 10 | raptor | 12 | 10 | RAPTOR; Raptor; raptor |
| 11 | TOR | 11 | 10 | TOR |
| 12 | Everolimus | 11 | 11 | Everolimus |
| 13 | S6K1 | 10 | 7 | S6K1 |
| 14 | TORC1 | 10 | 9 | TORC1; TORC1 inhibition |
| 15 | TFEB | 9 | 6 | TFEB |
| 16 | Rag | 9 | 9 | Rag |
| 17 | SLC38A9 | 9 | 5 | SLC38A9 |
| 18 | ULK1 | 7 | 5 | ULK1 |
| 19 | 4E-BP1 | 7 | 6 | 4E-BP1 |
| 20 | FLCN | 7 | 4 | FLCN |
| 21 | PRAS40 | 7 | 4 | PRAS40 |
| 22 | autophagy | 6 | 6 | Autophagy; autophagy |
| 23 | 4E-BP | 6 | 4 | 4E-BP |
| 24 | GATOR2 | 6 | 6 | GATOR2 |
| 25 | Ragulator | 6 | 5 | Ragulator |

## Zamítnuto (nejde o entity)

- `review` (29×)
- `cryo-EM` (11×)
- `Biochemical` (2×)
- `Genetic` (2×)
- `genetic` (1×)
- `>25-fold selective over mTORC2` (1×)
- `sparing mTORC2` (1×)
- `narrative review` (1×)

## AI_Species — kontrolovaný slovník

- Cell culture — 87
- Mouse — 73
- Human — 67
- Review (no model) — 33
- Structure / in vitro — 19
- Drosophila — 13
- UNMAPPED — 13
- Yeast — 7
- Rat — 5
- C. elegans — 5
- Zebrafish — 1
- Dog — 1

Nenamapováno (doplň pravidlo do SPECIES_MAP):

- `CRISPR screen; cells`
- `Cancer cell panels`
- `Cancer cells`
- `Cancer cells; tumor`
- `Cancer cells; xenograft`
- `Mammalian cell culture`
- `Multi-species`
- `N/A`
- `Rhesus macaque (2 independent cohorts)`
- `Skeletal muscle cells + tissue`
- `Streptomyces hygroscopicus (soil bacterium)`
