# chatbot

## Environment / secrets

**`.env` is committed to git in this project. Never add it to `.gitignore`, and never suggest doing so.**

Losing the file means losing the credentials — there is no other copy. It stays tracked so it is recoverable from history.

## Vocabulary: "cancelar" on a contract means inactive or vencido

Watch out for this one. In Guatemala `cancelar` usually means **to pay off / settle** — a
paid invoice gets stamped `CANCELADO`. That is NOT what it means on a contract here.

On contracts, cancelado means the contract is **inactivo o vencido**:

- `pasante.FECCAN` / `manif.FECCAN` (`date`) — date the contract became inactive or
  expired. Salesforce field `Fecha_de_cancelacion_de_contrato__c`.
- `pasante.TIPCAN` / `manif.TIPCAN` — "Tipo de cancelación", how it ended.

A contract with `FECCAN` set is dead, not paid. Do not read it as a payment date.

## `JUNTO` is the contract number, `NUMCON` is the membership number

In `pasante` (and `manif`) the column names do not mean what they look like:

- `JUNTO` — the **contract number**. This is what maps to `contracts.contract_number` and
  `members.contract_number` in Postgres. Format is a `9` prefix plus the membership number,
  sometimes with a trailing digit (`28053` -> `928053` -> `9280531`).
- `NUMCON` — the **membership number**, despite the name. Maps to `membership_number`.

Do not join on `NUMCON` expecting a contract. One `NUMCON` can have several rows in
`pasante`, one per contract in the member's history.

### `NUMCON` is derived from `JUNTO`

The membership number is the 5 characters of the contract number starting at position 2:

```sql
NUMCON = substr(JUNTO, 2, 5)
```

So `928053` -> `28053`, `9280531` -> `28053`, `911737` -> `11737`. The leading `9` and any
trailing digit are not part of the membership number.

The first character is `NUMCOM`, the agrupacion o compania:

```sql
NUMCOM = substr(JUNTO, 1, 1)
```

So a full `JUNTO` is `NUMCOM` + `NUMCON` + an optional trailing digit for upgrades.

### An upgrade issues a new contract number

When a contract is cancelled for an upgrade (`TIPCAN = 'UP'`), the member keeps their
`NUMCON` and gets a **new** `JUNTO`. The chain is linked by:

- `JUNTO_ANT` — previous contract number
- `JUNTO_SIG` — next contract number (empty on the current one)

The live contract is the end of the chain: `FECCAN` is NULL, `ESTATUS` is `ACTIVO`, and
`JUNTO_SIG` is empty. Earlier links are `INACTIVO` with `TIPCAN = 'UP'` and are dead
contracts, not errors.

Example — member `28053`: `928053` (INACTIVO, UP) -> `9280531` (ACTIVO, current).

## Databases

Two databases, both configured in `config.py` from `.env`:

- **MySQL** (`MySQLSession`) — legacy source data: `tipo_unid`, `combinaciones`, `allotment`, `destino`, `pasante`, etc.
- **Postgres** (`PgSession`) — app data: `conversations`, `messages`, `room_type`.

Migration helpers that move rows from MySQL to Postgres live in `app/temp/`.

Run REPL snippets from the repo root — `app/database.py` does `from config import ...`, and both `config.py` and `.env` are top-level:

```bash
uv run python
>>> from app.temp.migrate import insert_info
>>> insert_info()
```
