from typing import Final


class DSnakeWebCode:
    VERSION: Final[str] = "5.0.5"
    CMDB_TYPE: Final[str] = "Application"
    CMDB_SUBTYPE: Final[str] = "Website Publisher"
    CMDB_SUPPLIER: Final[str] = "Nadim-Daniel"
    CMDB_CODENAME: Final[str] = "Protactinium"
    CMDB_COMPONENTS: Final[tuple[tuple[str, str], ...]] = (
        ("Public Artifacts", "/var/lib/snake-web/public"),
    )
    CMDB_DATABASES: Final[tuple[tuple[str, str], ...]] = (
        ("Snake Lab", "snakelab"),
    )
    CMDB_NETWORK: Final[tuple[tuple[str, str, int], ...]] = (
        ("http", "192.168.0.106", 8080),
    )
    BASE_DIR: Final[str] = "/opt/prod/snakewebcode"
    CONFIG_FILE: Final[str] = "conf/snakewebcode.json"
    DAILY_GAME_LIMIT: Final[int] = 5
