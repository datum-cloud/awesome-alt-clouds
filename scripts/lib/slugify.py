"""Python mirror of src/lib/clouds.ts:slugify(). Must stay in sync.

Matches the TypeScript implementation byte-for-byte:
  1. lowercase
  2. NFKD normalize
  3. strip combining diacritical marks in the U+0300–U+036F block
  4. replace any non-alphanumeric run with `-`
  5. strip leading/trailing `-`
"""

import re
import unicodedata


_COMBINING_DIACRITICAL_MARKS = re.compile(r"[\u0300-\u036f]")
_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")
_TRIM_DASHES = re.compile(r"^-|-$")


def slugify(name: str) -> str:
    """Lowercase, dash-separated slug. Mirrors src/lib/clouds.ts:slugify()."""
    s = name.lower()
    s = unicodedata.normalize("NFKD", s)
    s = _COMBINING_DIACRITICAL_MARKS.sub("", s)
    s = _NON_ALNUM_RUN.sub("-", s)
    s = _TRIM_DASHES.sub("", s)
    return s
