# Coding Guidelines

Organize classes by responsibility within `snake_web`:

- **`entity/`** — Entity classes house data.
- **`activity/`** — Activity classes manipulate data and implement application
  operations.
- **`interface/`** — Interface classes communicate with external systems, such
  as databases and Snake Lab. `DbMgr` belongs here.
- **`server/`** — Wires components together and manages their lifecycle.
- **`constants/`** — Holds shared definitions.

## Data Abstraction Layer

The Data Abstraction Layer (DAL) follows this call flow:

**App → activity/AppDb → interface/DbMgr → database**

The app requests data in application terms, such as “get current high score.”
`AppDb` translates that request into SQL, calls `DbMgr`, and converts the
returned rows into an application value or entity. Query rules and the meaning
of the returned data belong in `AppDb`.

`DbMgr` manages database connections, parameterized SQL execution, transactions,
and connection cleanup. It returns rows without interpreting application
concepts such as high scores. The app does not call `DbMgr` directly.

For the publishing flow, the app obtains an `ExperimentStatus` through `AppDb`,
which reads Snake Lab simulations and Ax3l events using the read-only DAL.
It uses that result to regenerate the homepage. Page generation and Git
publishing remain outside the DAL.
