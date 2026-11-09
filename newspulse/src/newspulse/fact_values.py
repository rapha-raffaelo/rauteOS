"""Missing research is an open field, not an asserted fact."""
import re
_MISSING = re.compile(r'^(?:bitte ergänzen|noch zu ergänzen|nicht (?:öffentlich )?(?:veröffentlicht|verfügbar|bekannt|angegeben)|keine (?:öffentlichen |belegten )?angaben(?: vorhanden)?|unbekannt)[.!]?$',re.I)

def has_missing(value):
    if not value or not value.strip():
        return True
    return any(_ABSENT.search(line) or _MISSING.fullmatch(re.sub(r'^\s*[•*\-]\s+', '', line).split(':',1)[-1].strip())
               for line in re.split(r'\n|;\s*',value))


#: A sentence that reports a gap instead of a fact: "Zu Mitarbeiterzahl und
#: Umsatz gibt es keine öffentlichen Angaben." The model writes these although
#: told not to; each one becomes an open "bitte ergänzen" field, never prose.
_ABSENT = re.compile(r'\b(?:keine (?:öffentlich(?:en|e)? |belegten |belastbaren |weiteren )?(?:angaben|informationen|daten|zahlen)'
                     r'|nicht (?:öffentlich )?(?:bekannt|veröffentlicht|verfügbar|angegeben)|unbekannt)\b', re.I)
_SENTENCE = re.compile(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ])')
_TOPICS = (('Mitarbeitende', re.compile(r'mitarbeit|beschäftigt|personal', re.I)),
           ('Umsatz', re.compile(r'umsatz|erlös', re.I)))


def open_lines(line):
    """One line as facts and open fields: absent-sentences become "X: bitte ergänzen"."""
    if not _ABSENT.search(line) or _MISSING.fullmatch(line.split(':', 1)[-1].strip()):
        return [line]
    kept, gaps = [], []
    for sentence in _SENTENCE.split(line.strip()):
        if not _ABSENT.search(sentence):
            kept.append(sentence)
            continue
        named = [label for label, pattern in _TOPICS if pattern.search(sentence)]
        gaps += [f'{label}: bitte ergänzen' for label in named] or ['bitte ergänzen']
    return ([' '.join(kept)] if kept else []) + list(dict.fromkeys(gaps))
