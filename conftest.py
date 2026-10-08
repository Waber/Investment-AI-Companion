"""Load the application without a developer's ``.env`` for integration.

pytest imports this file before ``tests/conftest.py``. That second
file imports the application at module level, and ``Settings`` reads
``.env`` from the process working directory. When the command
selects the ``integration`` marker, the import below happens first,
from an empty temporary directory, so the file is never applied.

The default SQLite command does not select that marker. This file
then does not import the application, and the SQLite suite is
unchanged. ``tests/conftest.py`` is not modified.
"""

import sys
from pathlib import Path


def _isolate_when_integration_is_selected() -> None:
    root = str(Path(__file__).resolve().parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from tests.integration.env_isolation import (
        command_selects_integration,
        import_application_without_dotenv,
    )

    if command_selects_integration(sys.argv):
        import_application_without_dotenv()


_isolate_when_integration_is_selected()
