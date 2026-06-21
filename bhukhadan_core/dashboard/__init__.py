# -*- coding: utf-8 -*-

# Import abstract models (mixins) first - they must be loaded before the main model
from . import dashboard_helpers
from . import dashboard_counts
from . import dashboard_actions
from . import dashboard_data
from . import dashboard_stats
# Import main model last - it inherits from all the above mixins
from . import dashboard_base

