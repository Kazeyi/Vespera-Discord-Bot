import sys

INTERNED_STRINGS = {}

def intern_string(s: str) -> str:
    """
    Intern repeated strings to save memory.
    """
    if s not in INTERNED_STRINGS:
        INTERNED_STRINGS[s] = sys.intern(str(s))
    return INTERNED_STRINGS[s]
