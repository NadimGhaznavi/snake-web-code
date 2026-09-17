# Snake Web code

Python service that publishes Snake Lab scores, Ax3l experiment status, and a
saved high-score board to the
[Snake Web website](https://github.com/NadimGhaznavi/snake-web).
Application code, deployment scripts, DevOps documentation, and tests live here; website pages and
Jekyll configuration live in `snake-web`.

## Development

Run from the `snake-web-code` checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

## Deployment

Run `sudo scripts/install.sh` or `sudo scripts/upgrade.sh` from this checkout.
The installed service remains at `/opt/prod/snake-web` and publishes to a
separate `snake-web` checkout configured with `PUBLISH_CHECKOUT`.

See the [installation guide](docs/devops/install.md)
and [upgrade guide](docs/devops/upgrade.md)
for configuration and deployment details.

See [DevOps documentation](docs/devops/index.md) for all operational guides and coding guidelines.

## Static report slice

Top 100 displays the saved boards for up to 100 scored simulations, ordered by
high score descending and numeric run ID ascending for ties. Navigation below
each board wraps between the first and last available rank. The run label uses
the simulation's numeric ID, not its rank. Missing boards show a placeholder;
zero scores remain eligible and unscored runs are excluded. Each publication
refreshes this report, using the existing simulation read grant.

The homepage links to Experiment Highscores. Each publishing pass reads the
published CSV after synchronizing the site checkout, queries accepted scores
with a newer event ID, and appends them. The first pass exports the full accepted
score history. The browser fetches the static CSV and draws a Plotly spline plot
with hover and keyboard details, preserving lower scores after seed changes.
Plotly loads from its version-pinned CDN; smoothing changes only the connecting
line, while markers and CSV data retain the recorded scores.

Only event ID, simulation count, score, and seed are exported. Event-log payloads
and their sanitization are outside this slice. Export, report assets, and homepage
share one publication commit; failed pushes retry without duplicating records.
The service publishes on the hour and half hour in the server's local timezone,
starting at the next boundary after startup. It does not poll the database
between scheduled passes. `--once` still publishes immediately; unchanged
content does not create a new commit.

Upgrade provisioning adds SELECT access to `ax3l.experiment_highscores`.
The CSV assumes one continuous Ax3l database history with immutable accepted-score
records; replacing/resetting that database requires deliberately starting a new
export. Do not reuse an old CSV with reset event IDs.

The Score Distribution Histogram compares all scored runs with the oldest half
of submitted runs, matching Ax3l's shared bins (at most 40, minimum width 1).
The cohort split includes unscored runs and rounds down odd totals; null scores
are then excluded from bar counts. Zero remains a valid score.
Plotly renders the precomputed bins as overlapping blue and orange bars, with
hover counts and arrow-key navigation. It uses the same version-pinned CDN as
Experiment Highscores.

`reports/data/run-scores.csv` contains only numeric run IDs and nullable scores.
Because scores change while runs execute, each pass compares the database's
ID/score projection with the last exported observation for each run. New runs
and changed scores append observations; the browser uses the latest observation
per ID and orders runs by ID. Repeated publication does not duplicate records.
This reads all run IDs/scores each pass because the source has no score-change
cursor. The existing simulation table grant suffices; no new grant is needed.

The Golden Configurations table publishes every golden creation (initial/seed
baselines and promotions) in `reports/data/golden-configurations.csv`. New event
IDs append once; the browser displays newest timestamps first. Fields are event
ID, timestamp, run ID, score, formatted parameter/change, and only the first
choice's `message.reasoning_content`. Full responses, tool payloads, and raw
decision messages are not exported. Expand Reason to read preserved multiline
text. Configuration and simulation detail pages are not part of this slice.
The existing Ax3l read grants cover this report.

## Sanitized Event Log

The homepage's Event Log link opens a static, searchable report with category
and event filters and 100 entries per page. The export includes the entire
retained history, not only the last 500 events. Its explicit event allowlist is:

- SnakeLab / Simulation Completed
- Configuration / Golden Retained
- Conversation / Prompt
- Conversation / Response
- SnakeLab / Simulation Submitted

Prompts retain text and embedded PNGs; JSON text is pretty-printed in preformatted
blocks. Responses publish only first-choice `message.reasoning_content` and
numeric usage/timing metrics, including nested numeric counts. The reasoning
appears first; response envelopes, choices, assistant content, and tool-call
arguments are absent from the CSV as well as the page. Remaining event messages
and the displayed event metadata are retained. Text is rendered as text, never HTML.

Simulation Run details show the saved board, run ID, project version, high score,
and completion time. Submitted-configuration details use the explicit numeric
configuration schema. Both have Home and Event Log links. Provisioning adds
SELECT on `snakelab.configurations`; it does not change the source schema.

The managed files are `reports/event-log.html`, `reports/event-detail.html`,
`reports/event-log.js`, `reports/report-csv.js`, `reports/data/events.csv`,
`reports/data/event-simulations.csv`, and `reports/data/event-export.json`.
The versioned cursor records the highest source event examined, including
excluded types. Event queries use batches of 250 and a snapshot upper bound;
new retained events append once. Changed simulation details append observations,
and the browser uses the latest observation per run. Export and cursor changes
share the publication commit, so failed pushes can retry without duplicates.
Malformed prompts fail the export without advancing the cursor. CSV fields
larger than 64 MiB fail explicitly rather than being truncated.

As with the other incremental exports, source records must retain their IDs and
remain immutable. Resetting/replacing the source experiment requires a deliberate
new export; a cursor ahead of the source is rejected. Changes to sanitization
rules do not retroactively remove data from previously published files or Git
history. Browser pagination limits rendered rows; it still downloads the complete
CSV history. No live database-backed report service is required.

To start fresh against a different source database, use the
[site reset script](docs/devops/reset-site.md) to clear published data and cursors.
