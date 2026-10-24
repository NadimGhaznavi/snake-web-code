from typing import Final


class DSnakeWebCode:
    VERSION: Final[str] = "4.4.0"
    CMDB_TYPE: Final[str] = "Application"
    CMDB_SUBTYPE: Final[str] = "Website Publisher"
    CMDB_SUPPLIER: Final[str] = "Nadim-Daniel"
    CMDB_CODENAME: Final[str] = "Sulfur"
    CMDB_COMPONENTS: Final[tuple[tuple[str, str], ...]] = (
        ("Published Website", "/var/lib/snake-web/site"),
    )
    CMDB_DATABASES: Final[tuple[tuple[str, str], ...]] = (
        ("Snake Lab", "snakelab"),
        ("Ax3l", "ax3l"),
    )
    DAILY_GAME_LIMIT: Final[int] = 10
