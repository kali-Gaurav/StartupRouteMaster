# Redirection module to bridge broken imports
# This allows 'from database.session import ...' to work by delegating to 'database.infrastructure.session'

from .infrastructure.session import *
from .infrastructure.session import _dispose_all_pools
