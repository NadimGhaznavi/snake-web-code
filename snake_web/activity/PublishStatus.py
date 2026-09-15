"""Turn the current simulation high score into a published status page."""

import re


def render_status(content: str, score: int) -> str:
    if type(score) is not int or score < 0:
        raise ValueError("High score must be a nonnegative integer")
    pattern = r"(?m)^(- Current highscore: )[0-9]+([ \t]*\r?)$"
    if len(re.findall(pattern, content)) != 1:
        raise ValueError("Status page must contain exactly one current highscore line")
    return re.sub(pattern, lambda match: f"{match[1]}{score}{match[2]}", content)


class PublishStatus:
    def __init__(self, appdb, publisher):
        self._appdb = appdb
        self._publisher = publisher

    def run(self) -> str:
        score = self._appdb.get_current_highscore()
        if score is None:
            return "No recorded score; status page preserved"
        with self._publisher.session():
            content = self._publisher.read_status()
            changed = self._publisher.publish(render_status(content, score))
        return f"High score {score}: {'published' if changed else 'unchanged'}"
