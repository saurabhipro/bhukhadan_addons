# -*- coding: utf-8 -*-
"""
Loads split survey/mobile REST controllers under ``/api/bhuarjan/...``.

Importing this module registers all handlers; URL paths and HTTP methods are unchanged.
"""
from . import survey_api_helpers  # noqa: F401
from . import survey_api_org  # noqa: F401
from . import survey_api_reference  # noqa: F401
from . import survey_api_survey_read  # noqa: F401
from . import survey_api_landowner  # noqa: F401
from . import survey_api_survey_write  # noqa: F401
from . import survey_api_dashboard  # noqa: F401
