"""Missing research is an open field, not an asserted fact."""
import re
_MISSING = re.compile(r'^(?:bitte ergänzen|noch zu ergänzen|nicht (?:öffentlich )?(?:veröffentlicht|verfügbar|bekannt|angegeben)|keine (?:öffentlichen |belegten )?angaben(?: vorhanden)?|unbekannt)[.!]?$',re.I)

def has_missing(value):
    if not value or not value.strip():
        return True
    return any(_MISSING.fullmatch(re.sub(r'^\s*[•*\-]\s+', '', line).split(':',1)[-1].strip()) for line in re.split(r'\n|;\s*',value))
