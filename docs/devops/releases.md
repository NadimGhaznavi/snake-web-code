# Releases

The owner reviews and commits changes on a feature branch, then runs:

```sh
scripts/new-release.sh <version> "<codename>" [next-feature-branch]
```

Use a semantic version without a leading `v`. The supplied message becomes
`DSnakeWebCode.CMDB_CODENAME`; the commit and tag message is
`Release <version>: <codename>`. The script requires Git, Python 3, a clean
committed feature branch, and local `dev` and `main` branches. Merge `main` into
`dev` and `dev` into the feature branch before releasing. Local `main` and `dev`
must contain their corresponding remote branches when those exist.

The script fetches `origin` refs and tags, checks prerequisites, and shows the
source branch, tag, message, codename, next branch, and remote URL. An interactive
terminal and a `y` or `Y` response are required to proceed. Cancellation leaves
release files and branches unchanged; the fetch has already occurred.

After confirmation, it merges the feature branch into `dev`, updates the literal
version and codename in `snakewebcode/constants/DSnakeWebCode.py`, timestamps the
changelog's release heading, and commits those files. It merges `dev` into `main`, creates an
annotated `v<version>` tag, advances `dev` to `main`, and atomically pushes `main`,
`dev`, and that tag. It then creates the next local feature branch, defaulting to
`feat/maint-<version with patch incremented>`. Feature branches are not pushed.

Failures stop the script without rolling back prior steps. Inspect its output,
Git status, branch history, and remote refs before recovery; do not blindly rerun
after a failed push. The release script does not install code or publish website
data. Follow the [upgrade guide](upgrade.md) for deployment.
