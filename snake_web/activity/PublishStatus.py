"""Turn the current simulation high score into a published homepage."""

def render_status(score: int) -> str:
    if type(score) is not int or score < 0:
        raise ValueError("High score must be a nonnegative integer")
    return (
        "---\n"
        "title: Ax3l Experiment Status\n"
        "author_profile: true\n"
        "layout: single\n"
        "---\n\n"
        "# Experiment Status\n\n"
        f"- Current highscore: {score}\n"
    )


class PublishStatus:
    def __init__(self, appdb, publisher):
        self._appdb = appdb
        self._publisher = publisher

    def run(self) -> str:
        score = self._appdb.get_current_highscore()
        if score is None:
            return "No recorded score; homepage preserved"
        with self._publisher.session():
            changed = self._publisher.publish(render_status(score))
        return f"High score {score}: {'published' if changed else 'unchanged'}"
