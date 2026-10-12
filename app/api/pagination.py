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
# Largest signed 64-bit integer, the biggest INTEGER SQLite and PostgreSQL
# (BIGINT) store. A larger skip made SQLite fail with HTTP 500 (found in
# review of #19), so it is rejected with a 422 instead.
MAX_SKIP = 2**63 - 1

# Annotated[int, Query(...)] attaches extra metadata to a type. It is close
# to Bean Validation in Java: @Min/@Max on a method parameter. The type is
# still int for Python and mypy, and FastAPI reads the Query(...) part to
# validate the value and to document it in /docs. Defining it once here
# means the three list endpoints cannot drift apart, which is what repeating
# Query(...) in every signature would risk. The default value stays in the
# endpoint signature (skip: Skip = 0), as for any other parameter.
Skip = Annotated[
    int,
    Query(ge=0, le=MAX_SKIP, description="Number of records to skip."),
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
