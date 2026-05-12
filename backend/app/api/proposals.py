import sys

import app.api as _api_package
from app.plugins.proposal.backend import routes as _proposal_routes

# Compatibility shim: existing imports and tests that reference app.api.proposals
# are redirected to the proposal plugin implementation during the migration.
setattr(_api_package, "proposals", _proposal_routes)
sys.modules[__name__] = _proposal_routes
