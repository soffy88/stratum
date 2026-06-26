"""OpenStax open-access textbook search — Stratum-layer implementation.

API: https://openstax.org/apps/cms/api/v2/pages/?type=books.Book&format=json&fields=*
One request returns all 129 books with high_resolution_pdf_url directly.
No authentication required. CC license.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

_OPENSTAX_API = "https://openstax.org/apps/cms/api/v2/pages/"
_OPENSTAX_PDF_HOST = "https://assets.openstax.org"

# Subject names returned by OpenStax API
_DEFAULT_SUBJECTS = {"Math", "Science", "Computer Science", "Matemáticas", "Ciencia"}


def openstax_search(
    *,
    subjects: list[str] | None = None,
    keywords: str | None = None,
    book_state: str = "live",
    max_results: int = 50,
    max_pdf_mb: float = 0.0,
    rate_limit_sleep: float = 1.0,
) -> list:
    """Search OpenStax books. Returns list[SourceResult].

    subjects: e.g. ["Math", "Science"] — defaults to Math+Science+CS
    keywords: title keyword filter (case-insensitive)
    max_pdf_mb: 0 = no size filter (default); >0 = skip books above threshold
    """
    import time
    from oprim._media_types import SourceResult

    if rate_limit_sleep > 0:
        time.sleep(rate_limit_sleep)

    target_subjects = set(subjects) if subjects else _DEFAULT_SUBJECTS
    kw_lower = keywords.lower() if keywords else None

    params = {
        "type": "books.Book",
        "format": "json",
        "limit": "200",
        "fields": "*",
    }
    url = _OPENSTAX_API + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "stratum/1.0"},
        )
        data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as exc:
        log.warning("openstax_search: API request failed: %s", exc)
        return []

    results = []
    for book in data.get("items", []):
        if book.get("book_state") != book_state:
            continue

        title = book.get("title") or ""
        cnx_id = book.get("cnx_id") or book.get("book_uuid") or ""
        pdf_url = book.get("high_resolution_pdf_url") or ""
        slug = (book.get("meta") or {}).get("slug") or ""

        if not cnx_id or not pdf_url:
            continue

        # Check PDF size to avoid OOM in embedding stage (large color textbooks 50-80MB)
        if max_pdf_mb > 0:
            try:
                head = urllib.request.urlopen(
                    urllib.request.Request(pdf_url, method="HEAD",
                                          headers={"User-Agent": "stratum/1.0"}),
                    timeout=5,
                )
                size_mb = int(head.headers.get("Content-Length", 0)) / 1_048_576
                if size_mb > max_pdf_mb:
                    log.info("openstax_search: skip %r size=%.1fMB > %.0fMB limit",
                             title, size_mb, max_pdf_mb)
                    continue
            except Exception:
                pass  # if HEAD fails, include anyway

        # Subject filter
        subj_names = [
            s.get("subject_name", "") if isinstance(s, dict) else str(s)
            for s in (book.get("book_subjects") or [])
        ]
        if target_subjects and not any(s in target_subjects for s in subj_names):
            continue

        # Keyword filter
        if kw_lower and kw_lower not in title.lower():
            continue

        if len(results) >= max_results:
            break

        subjects_str = ",".join(subj_names)
        isbn = book.get("digital_isbn_13") or book.get("print_isbn_13") or ""
        license_name = book.get("license_name") or ""

        results.append(SourceResult(
            external_id=cnx_id,
            title=title,
            download_url=pdf_url,
            file_type="pdf",
            metadata={
                "source_type": "openstax",
                "openstax_slug": slug,
                "cnx_id": cnx_id,
                "subjects": subjects_str,
                "isbn": isbn,
                "license": license_name,
                "openstax_url": f"https://openstax.org/details/books/{slug}",
                "rex_url": book.get("webview_rex_link") or "",
            },
        ))

    log.info(
        "openstax_search: subjects=%s kw=%r → %d results",
        sorted(target_subjects),
        keywords,
        len(results),
    )
    return results
