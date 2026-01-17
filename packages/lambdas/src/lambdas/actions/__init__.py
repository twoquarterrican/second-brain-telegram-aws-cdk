"""Action modules for processing Telegram messages.

Each module exports a `handle(text, **kwargs)` function that processes
the message and returns a dict with statusCode and body.
"""

from .digest import handle as digest
from .open_items import handle as open_items
from .closed_items import handle as closed_items
from .debug_count import handle as debug_count
from .debug_backfill import handle as debug_backfill
from .debug_duplicates_auto import handle as debug_duplicates_auto
from .debug_duplicates import handle as debug_duplicates
from .merge import handle as merge
from .delete import handle as delete
from .process import handle as process
