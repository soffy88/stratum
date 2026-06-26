"""MIT OpenCourseWare lecture-notes search — Stratum-layer implementation.

Course list: https://api.learn.mit.edu/api/v1/learning_resources/?platform=ocw&department=18
Per-course PDFs: https://ocw.mit.edu/courses/{slug}/download/

Each course's /download/ page lists all PDFs. We filter to lecture-notes files
and return one SourceResult per PDF. external_id = "{slug}/{filename}" to allow
per-lecture deduplication across subscription scans.

Department codes:
  18 → Mathematics
   8 → Physics
   6 → EECS
   2 → Mechanical Engineering
   9 → Brain & Cognitive Sciences
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
import urllib.parse

log = logging.getLogger(__name__)

_LEARN_API = "https://api.learn.mit.edu/api/v1/learning_resources/"
_OCW_BASE = "https://ocw.mit.edu"

# Filename patterns for lecture notes (the part after the hash_)
_LECTURE_INCLUDE = re.compile(
    r"(^lec|lecture|^unit|^chapter|^notes|^handout|^slides|^ch\d|^class|"
    r"^l\d|u\d+_l\d+|wk\d)",
    re.I,
)
_LECTURE_EXCLUDE = re.compile(
    r"(exam|final|quiz|sol|answer|ans|problem_set|pset|ps\d|hw\d|homework|"
    r"review|recitation|rec\d|tutorial|lab\d|ta_notes)",
    re.I,
)

# MIT department numbers to readable labels
_DEPT_LABELS = {
    "18": "Mathematics",
    "8": "Physics",
    "6": "Electrical Engineering & Computer Science",
    "2": "Mechanical Engineering",
    "9": "Brain & Cognitive Sciences",
    "14": "Economics",
}


def _is_lecture_pdf(filename: str) -> bool:
    name = filename.rsplit(".", 1)[0].lower()
    # If the filename has hash_name pattern, check the name part
    parts = name.split("_", 1)
    check = parts[1] if len(parts) > 1 and len(parts[0]) == 32 else name
    return bool(_LECTURE_INCLUDE.search(check)) and not bool(_LECTURE_EXCLUDE.search(check))


def _get_course_pdfs(course_url: str, slug: str, course_title: str, max_pdfs: int) -> list[dict]:
    """Scrape /download/ page of a course and return list of PDF dicts."""
    download_url = f"{course_url.rstrip('/')}/download/"
    try:
        import http.client, ssl
        ctx = ssl.create_default_context()
        # Use http.client directly to control redirect following
        from urllib.parse import urlparse
        parsed = urlparse(download_url)
        conn = http.client.HTTPSConnection(parsed.netloc, timeout=15, context=ctx)
        conn.request("GET", parsed.path, headers={
            "User-Agent": "stratum/1.0",
            "Accept": "text/html",
            "Host": parsed.netloc,
        })
        resp = conn.getresponse()
        if resp.status in (301, 302, 307, 308):
            location = resp.getheader("Location") or ""
            # Only follow if it stays on same host (not /resources/ dead ends)
            if not location or "/resources/" in location:
                log.debug("mit_ocw: skipping redirect to dead-end %s", location)
                conn.close()
                return []
            # Follow one level
            parsed2 = urlparse(location)
            if not parsed2.netloc:
                parsed2 = parsed2._replace(netloc=parsed.netloc, scheme=parsed.scheme)
            conn2 = http.client.HTTPSConnection(parsed2.netloc, timeout=15, context=ctx)
            conn2.request("GET", parsed2.path, headers={"User-Agent": "stratum/1.0", "Accept": "text/html", "Host": parsed2.netloc})
            resp2 = conn2.getresponse()
            if resp2.status != 200:
                conn2.close()
                return []
            html = resp2.read().decode("utf-8", errors="replace")
            conn2.close()
        elif resp.status == 200:
            html = resp.read().decode("utf-8", errors="replace")
        else:
            return []
        conn.close()
    except Exception as exc:
        log.debug("mit_ocw: download page fetch failed %s: %s", download_url, exc)
        return []

    hrefs = re.findall(r'href=["\'](/courses/[^"\']+\.pdf)["\']', html, re.I)
    seen: set[str] = set()
    pdfs = []
    for href in hrefs:
        filename = href.rsplit("/", 1)[-1]
        if filename in seen:
            continue
        seen.add(filename)
        if _is_lecture_pdf(filename):
            pdfs.append({
                "url": _OCW_BASE + href,
                "filename": filename,
                "slug": slug,
                "course_title": course_title,
            })
        if len(pdfs) >= max_pdfs:
            break

    return pdfs


def mit_ocw_search(
    *,
    departments: list[str] | None = None,
    keywords: str | None = None,
    max_courses: int = 30,
    max_pdfs_per_course: int = 10,
    rate_limit_sleep: float = 1.5,
) -> list:
    """Search MIT OCW lecture notes. Returns list[SourceResult].

    departments: MIT dept codes e.g. ["18", "8"] — defaults to ["18"] (Math)
    keywords: title keyword filter (case-insensitive)
    max_courses: how many courses to scrape PDFs from
    max_pdfs_per_course: max lecture-note PDFs to yield per course
    """
    from oprim._media_types import SourceResult

    depts = departments or ["18"]
    kw_lower = keywords.lower() if keywords else None

    results = []

    for dept in depts:
        dept_label = _DEPT_LABELS.get(dept, f"dept-{dept}")
        offset = 0
        courses_used = 0

        while courses_used < max_courses:
            params = {
                "platform": "ocw",
                "department": dept,
                "resource_type": "course",
                "limit": "50",
                "offset": str(offset),
            }
            url = _LEARN_API + "?" + urllib.parse.urlencode(params)
            try:
                req = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json", "User-Agent": "stratum/1.0"},
                )
                data = json.loads(urllib.request.urlopen(req, timeout=15).read())
            except Exception as exc:
                log.warning("mit_ocw: API request failed dept=%s: %s", dept, exc)
                break

            items = data.get("results", [])
            if not items:
                break

            for course in items:
                if courses_used >= max_courses:
                    break

                title = course.get("title") or ""
                if kw_lower and kw_lower not in title.lower():
                    continue

                course_url = course.get("url") or ""
                readable_id = course.get("readable_id") or ""
                if not course_url:
                    continue

                # Skip RES (resource collections) — they have no /download/ page
                if readable_id.upper().startswith("RES."):
                    continue

                # slug = last path component of URL
                slug = course_url.rstrip("/").rsplit("/", 1)[-1]

                courses_used += 1  # count before fetch so max_courses cap is respected

                if rate_limit_sleep > 0:
                    time.sleep(rate_limit_sleep)

                pdfs = _get_course_pdfs(course_url, slug, title, max_pdfs_per_course)

                for pdf in pdfs:
                    ext_id = f"{slug}/{pdf['filename']}"
                    # Strip 32-char hash prefix for a readable label
                    raw_name = pdf['filename'].rsplit(".", 1)[0]
                    parts = raw_name.split("_", 1)
                    display = parts[1] if len(parts) > 1 and len(parts[0]) == 32 else raw_name
                    results.append(SourceResult(
                        external_id=ext_id,
                        title=f"{title} — {display}",
                        download_url=pdf["url"],
                        file_type="pdf",
                        metadata={
                            "source_type": "mit_ocw",
                            "course_title": title,
                            "course_url": course_url,
                            "department": dept,
                            "department_label": dept_label,
                            "readable_id": readable_id,
                            "filename": pdf["filename"],
                            "mit_ocw_slug": slug,
                        },
                    ))

            if not data.get("next"):
                break
            offset += 50

    log.info(
        "mit_ocw_search: depts=%s kw=%r → %d PDFs",
        depts, keywords, len(results),
    )
    return results
