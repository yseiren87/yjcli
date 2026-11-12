---
name: yj-secure-coding
description: >-
  Baseline secure-coding rules for every platform: secrets, hashing and
  encryption, passwords, logging and error exposure, exception handling,
  deserialization, randomness, resources and file permissions. Load together
  with the platform skill when writing, modifying or reviewing code.
---

# yj-secure-coding

Requires `yj-arch-core`. Short, scanner-independent rules; they hold in every language. Project-specific security rules (e.g. a scanner's exact patterns) go in `.yjcli/skills/yj-secure-coding.md`.

## Secrets

- Never hardcode credentials, API keys, tokens or salts — not even in tests. Read them from the environment (env value files); test-only values are named constants read from the environment too.
- Never log, print or return secrets; never copy env values into code, docs or commit messages.

## Hashing, encryption, passwords

| Use | Required | Forbidden |
|---|---|---|
| Hash | SHA-256 or stronger, combined with a salt (`sha256(f"{SALT}:{value}")`); a fixed salt from the environment keeps lookups deterministic | MD5, SHA-1, unsalted hashes |
| Reversible data (keys, tokens, credentials) | AES-256-GCM with a fresh random nonce per encryption | ECB/CBC or other unauthenticated modes, home-made crypto, reused or fixed nonces |
| User passwords | bcrypt (or argon2/scrypt) | plain SHA hashes, reversible encryption |

- Changing a salt or key derivation invalidates stored hashes/ciphertexts: find where they are stored and plan the recomputation first.

## Authentication

- Never base an access decision on hostnames or reverse DNS; use signed tokens or allowlisted addresses.
- Credential endpoints get rate limiting per client (IP) in addition to account lockout.
- Password inputs set `autocomplete` explicitly (`current-password`, `new-password` or `off`).

## Logging and error exposure

- Do not pass user-controlled values (paths, ids from requests, free text, validation errors) into logs as is: log a reduced form (length, type, id) or strip newlines and control characters.
- Do not print stack traces or raw exception objects to users or logs (`traceback.print_exc()`, `print(e)`, `console.log(err)` on a response path); log the exception type and context.
- No leftover debug output (prints, debug dumps) in committed code.

## Exceptions

- Catch the specific exceptions that can occur. A catch-all only at real boundaries (request entry, background loop, health check), where it logs and degrades instead of crashing.
- Never leave a catch block empty (a comment alone is still empty): handle, log or rethrow.
- Do not use `assert` for runtime validation (it is stripped with optimizations); raise an explicit error.

## Data and resources

- Deserialize safely: `yaml.safe_load`, JSON; never `pickle`/`marshal` or unsafe YAML loaders on data from outside the process.
- Build queries with parameters or structured filters, never by string concatenation; do not pass user input to shells or `eval`.
- Open files, sockets and connections in scoped blocks (`with`, `defer`, `try/finally`, `using`).
- Security-relevant random values come from a CSPRNG (`secrets`, `crypto.getRandomValues`, `crypto/rand`), never `random`/`Math.random()`.
- Set restrictive permissions when a sensitive file is created (`mkstemp`, `os.open(..., 0o600)`), instead of creating it open and tightening it later.
