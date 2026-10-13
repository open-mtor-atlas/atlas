# mTOR Atlas MCP server

Read-only access to [Oliver's mTOR Atlas](https://mtor-atlas.org) for AI assistants that speak the
[Model Context Protocol](https://modelcontextprotocol.io): curated mTOR studies labelled by the kind of
study behind them, entities (genes, complexes, drugs, diseases, processes), signed pathway relations with
their supporting and conflicting evidence, and the Atlas's open questions.

The server reads the Atlas's public static API (`https://mtor-atlas.org/api/v1/`, documented at
[mtor-atlas.org/api](https://mtor-atlas.org/api/)). No key, no account. Data is CC BY 4.0.

## Install

Claude Desktop, Claude Code, Cursor and other MCP clients:

```json
{
  "mcpServers": {
    "mtor-atlas": { "command": "npx", "args": ["-y", "mtor-atlas-mcp"] }
  }
}
```

Claude Code: `claude mcp add mtor-atlas -- npx -y mtor-atlas-mcp`

## Tools

| Tool | What it answers |
|---|---|
| `atlas_about` | Dataset version, corpus snapshot, counts, evidence codes, how to cite; `derived_counts` for contested and conflicting relations |
| `search_studies` | Studies by keywords, evidence code, linked entity, year |
| `get_study` | One study with its entities, relations and open questions |
| `search_entities` / `get_entity` | Genes, drugs, diseases… with their studies and relations. Each hit says where it matched (`match_field`); `match="name"` skips description-only hits |
| `find_relations` / `get_relation` | Pathway claims ("Rheb activates mTORC1") with mechanism, boundary conditions and confidence |
| `evidence_between` | "What is the evidence that A acts on B?" with both supporting and conflicting studies |
| `find_contradictions` | Contested claims, with both sides of the evidence. Paged (`offset`), `status` and `breakdown` explain the total, `only_contested`, `brief` |
| `list_questions` / `get_question` | Open evidence gaps and testable hypotheses. `list_questions` is paged and shortens `still_open` unless `brief=false`; `get_question` has the full text |

## Answer size

Long text and repeated records are kept short by default. `list_questions` cuts `still_open` at a sentence boundary and sets `still_open_truncated`; `find_contradictions` and `evidence_between` send a study in full the first time it appears in an answer and afterwards as a short card (sid, title, evidence code with its label, url) with `full_card_in`. Pass `brief=false` or `dedupe=false` to get everything. Every list tool takes `limit` and `offset`; pass `next_offset` back as `offset` for the next page.

## Reading the evidence codes

S synthesis of human data · H human study · A animal model · M molecular / in vitro · R review ·
PP preprint · RT registered trial. **The code describes the kind of study, not its quality.** Every
record the server returns repeats this, so a code never travels without its meaning.

"Not in the Atlas" means not in this curated corpus. It does not mean the relationship is unknown.

## Cite

Barton O. *Oliver's mTOR Atlas.* doi:[10.5281/zenodo.22059963](https://doi.org/10.5281/zenodo.22059963).
Give the `dataset_version` and `corpus_snapshot` returned by `atlas_about`.

## Configuration

`ATLAS_API_BASE` (optional) points the server at another copy of the API, for example a local
build: `ATLAS_API_BASE=/path/to/dist/api/v1`.

Code: MIT. Data: CC BY 4.0.
