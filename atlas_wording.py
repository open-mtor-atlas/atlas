# -*- coding: utf-8 -*-
"""Zakazane formulace Atlasu -- JEDEN seznam pro vsechny brany.

Audit 11. 10. 2026 nasel, ze validate_claims.py a check_consistency.py
mely KAZDA svuj dvanactiprvkovy seznam a jejich PREKRYV BYL NULOVY:
jeden resil silu dukazu ("proves", "definitive", "conclusive"), druhy
marketingovy superlativ ("the single most", "the best-known way").
Dohromady s tim, ze kazda brana cetla jinou mnozinu poli, z toho vznikla
mezera: veta "Rapamycin proves that mTOR inhibition extends human
lifespan" v beginner textu hrany prosla obema branami. Overeno testem,
ne odhadem.

Odted obe brany importuji odsud. Kdyz pridavas vzor, pridavas ho pro
celou pipeline, ne pro jednu branu.
"""
import re

# Sila dukazu: slovo tvrdi vic, nez muze jedna studie unest.
EVIDENCE_STRENGTH = {
    r"\bprove[sd]?\b": "show / support",
    r"\bproven\b": "supported",
    r"\bproof\b": "evidence",
    r"\bdefinitiv(e|ely)\b": "landmark / strongest available",
    r"\bconclusiv(e|ely)\b": "consistent with",
    r"\bunequivocal(ly)?\b": "clear",
    r"\bbeyond doubt\b": "well supported",
    r"\bsettle[sd]?\b": "address / weigh in on",
    r"\bestablishes? (that|beyond)\b": "supports that",
    r"\bdirect (clinical )?confirmation\b": "evidence consistent with",
    r"\bempirically confirming\b": "consistent with",
    r"\bguarantee[sd]?\b": "makes likely",
}

# Marketingovy superlativ: zadny absolutismus o vyznamu ci prvenstvi.
SUPERLATIVE = {
    r"\bthe single most\b": "one of the most",
    r"\bthe one thing\b": "one of the things",
    r"\bthe entire (?:mTOR )?field\b": "much of the field",
    r"\bthe whole story of\b": "part of the story of",
    r"\bonly at the lysosome\b": "chiefly at the lysosome",
    r"\bis only switched on here\b": "is switched on here",
    r"(?<!one of )(?<!among )\bthe most (?:conserved|reliable|important|precise|drug-friendly|pharmacologically)\b": "one of the most ...",
    r"\bpioneer(?:ed)? of\b": "early work on",
    r"\bthe leading longevity\b": "a leading longevity",
    r"\bthe best-known way\b": "a well-known way",
    # Urcity clen je ten problem. "one of several founding papers" je
    # spravna kalibrace -- Inoki 2003, Shaw 2004 i Corradetti 2004 vznikly
    # nezavisle -- a nesmi padat do stejne pasti.
    r"(?<!one of )(?<!among )\bthe founding papers?\b": "one of the founding papers",
    r"\bbirth of the field\b": "early years of the field",
}

#: Vsechno dohromady. Tohle importuji brany.
FORBIDDEN = dict(EVIDENCE_STRENGTH)
FORBIDDEN.update(SUPERLATIVE)


# ---------------------------------------------------------------------------
# Scanner. Sdili se STEJNE jako seznam vzoru -- 11. 10. 2026 jsem nejdriv
# sdilel jen data a check_consistency zacala hlasit 16 nalezu, z nichz
# vetsina byla prave ta spravna opatrnost: "exactly how GATOR2 suppresses
# GATOR1 is still NOT settled", "that the tumour responds is NOT proof that
# mTORC1 initiates the cancer". Negovane uziti silneho slova je to opatrne
# uziti; flagovat ho znamena tlacit Atlas, aby hedgoval i svoje vlastni
# nulove vysledky. Logika proto patri k seznamu, ne do kazde brany zvlast.
NEGATION = re.compile(r"\b(not|never|no|nor|without|lacking|absent|yet to|fails? to|"
                      r"cannot|can't|isn't|is not|does not|did not|unable to|"
                      r"rather than|instead of)\b", re.I)


def negated(text, start):
    """True, kdyz shoda na pozici `start` sedi v negaci."""
    return bool(NEGATION.search(text[max(0, start - 70):start])
                or NEGATION.search(text[start:start + 40]))


def scan(text, patterns=None):
    """Vrati [(nalezene_slovo, navrh_nahrady, pozice)] bez negovanych uziti."""
    out = []
    if not text:
        return out
    for pat, fix in (patterns or FORBIDDEN).items():
        for m in re.finditer(pat, text, re.I):
            if not negated(text, m.start()):
                out.append((m.group(0), fix, m.start()))
    return out
