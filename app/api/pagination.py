"""Shared bounds for the skip and limit query parameters of list endpoints.

Issue #19: skip and limit used to be plain ints. A negative limit reached
SQL as LIMIT -1, and SQLite treats that as "no limit", so one request could
read a whole table. A huge limit had the same effect. FastAPI now rejects
out-of-range values with a 422 before the endpoint body runs.
"""

from typing import Annotated

from fastapi import Query

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 1000

# Annotated[int, Query(...)] attaches extra metadata to a type. The type is
# still int for Python and mypy, and FastAPI reads the Query(...) part to
# validate the value and to document it in /docs. Defining it once here
# means the three list endpoints cannot drift apart, which is what repeating
# Query(...) in every signature would risk. The default value stays in the
# endpoint signature (skip: Skip = 0), as for any other parameter.
Skip = Annotated[
    int,
    Query(ge=0, description="Number of records to skip."),
]
Limit = Annotated[
    int,
    Query(
        ge=1,
        le=MAX_PAGE_LIMIT,
        description=(
            f"Maximum number of records to return (1 to {MAX_PAGE_LIMIT})."
        ),
    ),
]
