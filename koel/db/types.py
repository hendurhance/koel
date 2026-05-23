from sqlalchemy.types import UserDefinedType


class CITEXT(UserDefinedType[str]):
    """Case-insensitive text. Maps to Postgres CITEXT (requires `CREATE EXTENSION citext`)."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "CITEXT"

    def bind_processor(self, dialect: object) -> None:
        return None

    def result_processor(self, dialect: object, coltype: object) -> None:
        return None
