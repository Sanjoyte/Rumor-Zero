"""Source validation: an http(s) URL or a DOI, normalised for storage (ARCHITECTURE §4c).

Pure functions, no DRF and no I/O: **a source is never fetched**. The browser mirrors this file
step for step in `frontend/src/features/posts/sources.ts`; both are driven by the shared vectors in
`apps/posts/tests/source_vectors.json`, so they can't drift apart. The browser's own `URL` parser is
deliberately *not* the algorithm: it turns `\\` into `/`, decodes `%xx` in hosts and accepts
`https:example.com`.
"""

import re
import unicodedata
from urllib.parse import quote

import idna
from django.core.exceptions import ValidationError

from apps.posts.models import MAX_SOURCE_LENGTH, MAX_SOURCES

# Raw input longer than this is refused before any work (the stored value is at most 500).
MAX_RAW_LENGTH = 2000
# JS trim() and Python strip() disagree on U+FEFF, U+001C-001F and U+0085, so trim only these.
ASCII_WHITESPACE = " \t\r\n"
# Cc control, Cf format (bidi marks), Cs surrogate, Zs/Zl/Zp spaces and separators.
FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zs", "Zl", "Zp"})

# [0-9], not \d (Unicode digits); fullmatch, not $ (a trailing newline); no IGNORECASE (the Kelvin
# sign and the long s would match). Crossref's recommended pattern.
DOI_PATTERN = re.compile(r"10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+")
# ASCII-only case folding, for the same reason (`httpſ://` must not read as https).
DOI_PREFIX = re.compile(r"(?:doi:[ \t]*|https?://(?:dx\.)?doi\.org/)", re.IGNORECASE | re.ASCII)
# RFC 3986 appendix B. The same expression is used in the browser (an identical split).
URI_PATTERN = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*):(?://(?P<authority>[^/?#]*))?"
    r"(?P<path>[^?#]*)(?P<query>\?[^#]*)?(?P<fragment>#.*)?"
)
LABEL_PATTERN = re.compile(r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?")
PORT_PATTERN = re.compile(r"[0-9]{1,5}")
# WHATWG reads a host whose last label is a number as IPv4: 127.1, 0x7f.1, 1.2.3.4.
NUMERIC_LABEL = re.compile(r"[0-9]+|0x[0-9a-f]*")
DEFAULT_PORTS = {"http": 80, "https": 443}

HELP_LINK = "Enter a link that starts with https:// or http://, or a DOI such as 10.1000/xyz."
HELP_DOI = "That doesn't look like a DOI. A DOI looks like 10.1000/xyz."
HELP_HOST = "Enter a full website address, such as example.org."
HELP_IP = "Links to IP addresses and localhost aren't allowed."
HELP_CREDENTIALS = "Links with a username or password aren't allowed."


def _invalid(message=HELP_LINK, code="invalid_source"):
    return ValidationError(message, code=code)


def source_kind(value):
    """`doi` for a stored bare DOI (it starts with `10.`), `url` otherwise (it starts with http)."""
    return "doi" if value.startswith("10.") else "url"


def normalize_source(value):
    """Return the stored form of one source, or raise `ValidationError` (with a code)."""
    if not isinstance(value, str):
        raise _invalid()
    value = value.strip(ASCII_WHITESPACE)
    if not value:
        raise _invalid("This source is empty.", "empty_source")
    if len(value) > MAX_RAW_LENGTH:
        raise _too_long()
    doi = _as_doi(value)
    if doi is not None:
        return _limited(doi)
    _check_characters(value)
    return _limited(_normalize_url(value))


def _too_long():
    return _invalid(
        f"This source is too long ({MAX_SOURCE_LENGTH} characters at most).", "source_too_long"
    )


def _limited(value):
    if len(value) > MAX_SOURCE_LENGTH:
        raise _too_long()
    return value


def _as_doi(value):
    """The bare DOI when the input is one, None when it is an ordinary URL."""
    prefix = DOI_PREFIX.match(value)
    if prefix:
        rest = value[prefix.end() :]
        if DOI_PATTERN.fullmatch(rest):
            return rest
        if prefix.group().lower().startswith("doi:"):
            raise _invalid(HELP_DOI, "invalid_doi")
        return None  # a doi.org link that isn't a plain DOI (a query, say) is an ordinary URL
    if value.startswith("10."):
        if DOI_PATTERN.fullmatch(value):
            return value
        raise _invalid(HELP_DOI, "invalid_doi")
    return None


def _check_characters(value):
    for char in value:
        if char == "\\" or unicodedata.category(char) in FORBIDDEN_CATEGORIES:
            raise _invalid("Links can't contain spaces, backslashes or hidden characters.")


def _normalize_url(value):
    match = URI_PATTERN.fullmatch(value)
    if not match or match["scheme"].lower() not in DEFAULT_PORTS or match["authority"] is None:
        raise _invalid()
    scheme = match["scheme"].lower()
    authority = match["authority"]
    if "@" in authority:
        raise _invalid(HELP_CREDENTIALS)
    host, separator, port = authority.rpartition(":")
    if not separator:
        host, port = authority, None
    elif not PORT_PATTERN.fullmatch(port) or not 1 <= int(port) <= 65535:
        raise _invalid("That link's port number isn't valid.")
    host = _normalize_host(host)
    netloc = host
    if port is not None and int(port) != DEFAULT_PORTS[scheme]:
        netloc += f":{int(port)}"
    rest = (match["path"] or "/") + (match["query"] or "") + (match["fragment"] or "")
    # Only non-ASCII characters are percent-encoded (UTF-8, uppercase hex); the rest stays as typed.
    rest = "".join(quote(char, safe="") if ord(char) > 127 else char for char in rest)
    return f"{scheme}://{netloc}{rest}"


def _normalize_host(host):
    if not host:
        raise _invalid("That link has no website address.")
    if any(char in host for char in "%[]"):
        raise _invalid(HELP_IP if "[" in host else HELP_HOST)
    if host.isascii():
        host = host.lower()
    else:
        try:
            host = idna.encode(host, uts46=True).decode("ascii")
        except (idna.IDNAError, UnicodeError):
            raise _invalid(HELP_HOST) from None
    labels = host.split(".")
    if host == "localhost" or host.endswith(".localhost") or NUMERIC_LABEL.fullmatch(labels[-1]):
        raise _invalid(HELP_IP)
    if len(labels) < 2 or len(host) > 253 or not all(LABEL_PATTERN.fullmatch(x) for x in labels):
        raise _invalid(HELP_HOST)
    for label in labels:
        if label.startswith("xn--"):
            try:
                idna.decode(label)
            except (idna.IDNAError, UnicodeError):
                raise _invalid(HELP_HOST) from None
    return host


def validate_sources(values):
    """Normalise a list of sources: at most 5, each valid, none repeated. Order is kept.

    Raises `ValidationError` with `too_many_sources` for the list itself, or a dict
    `{"<index>": [errors]}` collecting **every** bad element (and `duplicate_source` on the later of
    two equal ones: "Same as source 1"). URLs compare exactly after normalising; DOIs compare
    case-insensitively.
    """
    if not isinstance(values, (list, tuple)):
        raise ValidationError("Sources must be a list.", code="invalid_sources")
    if len(values) > MAX_SOURCES:
        raise ValidationError(f"You can add up to {MAX_SOURCES} sources.", code="too_many_sources")
    errors = {}
    cleaned = []
    for index, value in enumerate(values):
        try:
            cleaned.append(normalize_source(value))
        except ValidationError as exc:
            errors[str(index)] = exc.error_list
            cleaned.append(None)
    first_seen = {}
    for index, value in enumerate(cleaned):
        if value is None:
            continue
        key = value.lower() if source_kind(value) == "doi" else value
        if key in first_seen:
            message = f"Same as source {first_seen[key] + 1}."
            errors[str(index)] = [ValidationError(message, code="duplicate_source")]
        else:
            first_seen[key] = index
    if errors:
        raise ValidationError(errors)
    return cleaned
