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
