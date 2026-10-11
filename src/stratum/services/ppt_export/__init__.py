"""Book → editable lecture PPT export.

The pipeline has three halves with a hard boundary between them:

1. ``material`` reads what AII already understood about a book (BU2 chapter
   understandings, the P13 synthesis, the parsed chapter text). Nothing is
   re-read from the original file and nothing is invented here.
2. ``deck_builder`` asks the configured model to turn that material into a
   luobo-ppt ``deck.json`` (conclusion titles, on-screen key points, speaker
   notes), then validates, language-checks and fits it to the layout limits.
3. ``engine`` runs the vendored luobo-ppt scripts (plan → assets → build → QA)
   as subprocesses. They are deterministic and need no network or image model.

``jobs`` wraps the three in an asynchronous, owner-scoped job.
"""

from stratum.services.ppt_export.styles import list_styles, style_ids

__all__ = ["list_styles", "style_ids"]
