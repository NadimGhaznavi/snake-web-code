# Publish immediately

Run from the `snake-web-code` checkout to publish immediately using the
installed code and service credentials:

```sh
sudo scripts/push-now.sh
```

The script displays the result and returns a nonzero exit status on failure.
It leaves scheduled publishing running and creates no commit for unchanged
content. If a scheduled publication is already in progress, rerun after it
finishes. [Upgrade first](upgrade.md) if you want to publish changes from this
checkout.

Manual publication does not collect daily chart observations. The chart retains
its last scheduled animation, while game rankings and other reports refresh.
The next scheduled half-hour pass collects the next chart frame.
