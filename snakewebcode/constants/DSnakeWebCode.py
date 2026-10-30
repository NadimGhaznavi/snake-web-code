from typing import Final


class DSnakeWebCode:
    VERSION: Final[str] = "5.0.1"
    CMDB_TYPE: Final[str] = "Application"
    CMDB_SUBTYPE: Final[str] = "Website Publisher"
    CMDB_SUPPLIER: Final[str] = "Nadim-Daniel"
    CMDB_CODENAME: Final[str] = "Thallium"
    CMDB_COMPONENTS: Final[tuple[tuple[str, str], ...]] = (
        ("Public Artifacts", "/var/lib/snake-web/public"),
    )
    CMDB_DATABASES: Final[tuple[tuple[str, str], ...]] = (
        ("Snake Lab", "snakelab"),
    )
    DAILY_GAME_LIMIT: Final[int] = 5
