"""Aggregate router definitions.

Import all router modules here so that they can be easily included
within the application. When new routers are added to the project,
ensure they are imported in this file.
"""

from . import auth  # noqa: F401
from . import services  # noqa: F401
from . import providers  # noqa: F401
from . import clients  # noqa: F401
from . import locations  # noqa: F401
from . import bookings  # noqa: F401
from . import availability  # noqa: F401
from . import admin_dashboard  # noqa: F401
from . import public_bootstrap  # noqa: F401
from . import audit  # noqa: F401
from . import payments  # noqa: F401
from . import notifications  # noqa: F401

# New feature routers
from . import holds  # noqa: F401
from . import waitlist  # noqa: F401
from . import search  # noqa: F401
from . import ui_config  # noqa: F401
from . import forms  # noqa: F401
from . import diagnostics  # noqa: F401
from . import categories  # noqa: F401
from . import resources  # noqa: F401
from . import addons  # noqa: F401
from . import products  # noqa: F401
from . import packages  # noqa: F401
# intentionally omitted from the aggregated imports.  If recurring bookings are
# needed in future, a complete implementation should be added before
# re‑enabling this router.
from . import public_bookings  # noqa: F401
