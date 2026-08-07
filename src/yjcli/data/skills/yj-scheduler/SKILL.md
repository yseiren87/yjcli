---
name: yj-scheduler
description: >-
  Long-running scheduler architecture for multiple periodic batch jobs. Use
  only when editing scheduler/**. Language-agnostic: use an established
  scheduling framework from the project's ecosystem without prescribing a
  specific library. Covers job registration, execution isolation, overlap,
  misfires, timezones, retries, locks, observability, and graceful shutdown.
  Do not use for backend/, backend-service/, frontend/, mobile-app/, pc-app/,
  cli/, or browser-extension/.
---

# yj-scheduler

Requires `yj-arch-core`. Scope: **`scheduler/` only**.

## Purpose

Run multiple recurring batch jobs in one or more long-running scheduler
processes. Use an established scheduling framework from the selected language
ecosystem. Choose the concrete framework from the repository's stack and
existing dependencies.

Do not implement cron parsing, durable scheduling, misfire handling, or a
`while` + `sleep` scheduling loop from scratch.

## Shape

```text
scheduler/
  scripts/                     # platform-level only
  {scheduler_name}/            # one deployable scheduler process
    apps/                      # entry: boot, registration, wiring, shutdown
    services/
      {job_name}/              # one batch workflow
    domains/                   # optional: owned concepts only
    modules/                   # scheduler adapter, db/api clients, lock, clock
```

- One scheduler process may register multiple related jobs.
- Split jobs into separate `{scheduler_name}` deployables only when they need
  independent deployment, scaling, dependencies, permissions, or failure isolation.
- Do not add per-job `scripts/` or Makefiles. Root `make scheduler` runs all
  scheduler services; `NAME=<scheduler_name>` runs one.
- This is a long-running worker platform. `HOST` and `PORT` are optional and
  should exist only when the process exposes a real endpoint.

## Roles

### entry (`apps`)

- Create and configure the scheduling framework, register triggers, wire job
  handlers, start the process, and perform graceful shutdown.
- Keep registration declarative and discoverable in one entry area.
- Framework callbacks must be thin: add execution context, call one flow, and
  report its result. No query, transformation, or persistence logic in callbacks.

### flow (`services/{job_name}`)

- Each periodic job is an independently testable workflow.
- Own job-specific input, orchestration, batching, checkpointing, and result shape.
- A failure in one job must not terminate or block unrelated jobs.
- Make operations idempotent whenever a retry or duplicate trigger is possible.

### domain / infra

- Add `domains/` only for concepts or shared policy owned by this process;
  persistence is not required. Do not create a domain merely because a job exists.
- Put framework integration, distributed locks, clocks, persistence, logging,
  and external clients in `modules/`.
- Do not import another platform's source tree; communicate through explicit
  APIs or generated contracts.

## Scheduling policy

For every job, make these decisions explicit near its registration or config:

- stable job identifier and handler
- periodic or calendar trigger and explicit timezone
- whether overlapping executions are allowed
- misfire behavior (skip, coalesce, or catch up)
- timeout, retry, and backoff behavior
- concurrency limit and multi-instance ownership/locking strategy

Never rely implicitly on the host's local timezone. Do not scatter schedule
expressions across callbacks. Fixed business schedules may live in typed code or
project configuration; expose them as environment-specific settings only when
deployments genuinely need different schedules.

When more than one scheduler instance can run, use the framework's persistent
job store/single-run facility or a distributed lock. A process-local mutex does
not prevent duplicate execution across instances.

## Reliability and observability

- Log job id, execution/run id, scheduled time, actual start, completion or
  failure, duration, and retry attempt using structured fields.
- Define shutdown behavior: stop accepting triggers, then finish or safely
  cancel active jobs within a bounded grace period.
- Long-running or high-volume jobs should use bounded batches and checkpoints so
  they can resume safely after interruption.
- Keep retry scope narrow. Do not retry permanent validation or authorization
  failures as though they were transient infrastructure failures.
- Inject or wrap the clock in flow/domain tests; do not make business rules
  depend directly on wall-clock calls throughout the codebase.

## Import direction

```text
entry/framework callback -> flow -> domain? -> infra
entry -> infra
flow  -> infra
```

Forbidden: business logic in trigger callbacks; flow importing entry/framework
bootstrap; domain importing scheduler framework types; jobs calling one another
for sequencing when a single coordinating flow owns the workflow.

## Editing scope

- Stay within `scheduler/{scheduler_name}/` unless the task explicitly changes
  shared contracts or platform wiring.
- Prefer extending an existing scheduler process for related jobs; do not create
  one deployable per cron expression automatically.
