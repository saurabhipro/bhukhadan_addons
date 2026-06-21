# -*- coding: utf-8 -*-
"""REST and HTTP JSON controllers (mobile app, Form 10, uploads, docs)."""
from . import main  # noqa: F401 — shared helpers; load before survey_api / auth
from . import qr_microsite  # noqa: F401
from . import survey_api  # noqa: F401 — /api/bhuarjan/* mobile REST bundle
from . import survey_form10_pdf_api  # noqa: F401
from . import survey_form10_excel_api  # noqa: F401
from . import auth  # noqa: F401
from . import file_upload_api  # noqa: F401
from . import api_docs  # noqa: F401
from . import project_controller  # noqa: F401
