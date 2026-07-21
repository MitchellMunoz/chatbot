# Make the chatbot actually use its tools — teaching guide

Mitch writes all code. This file explains the concepts and gives the shapes to type.

## Lesson 0 — Why your bug happens

`stop_reason == "tool_use"` does NOT mean "Claude answered." It means **"Claude paused
mid-thought and is asking YOUR server to run a function and report back."** Tool use is a
two-phase protocol:

```
user:      "¿Hay doble en Antigua del 20 al 22?"
assistant: [tool_use block: check_availability({hotel:"antigua", ...})]   ← Claude's REQUEST
user:      [tool_result block: '{"available": true, "nights": 2}']        ← YOUR code answers it
assistant: "¡Sí! Tenemos disponibilidad para esas fechas..."              ← the real answer
```

Your current `generate_response` treats phase 1 as the final answer, returns the stub string
"Claude wants to use the tool: X", and routes.py saves that stub into Postgres as an assistant
message. Next turn, Claude reads its own history, sees itself "talking" like that, and imitates
it. That's why the bot derails — the history is poisoned.

The fix is the **agentic loop**: keep calling the API, executing tools, and feeding results back
until Claude stops asking for tools and produces text.

## Lesson 1 — How your app talks to MySQL (this already exists!)

In `app/database.py` you already built everything needed:

- **Engine** (`create_engine(url_mysql)`) = the phonebook + a pool of reusable phone lines to the
  DB. Created once at import. Your URL says: driver `mysql+pymysql`, host `127.0.0.1:3307` —
  that's not a local database, it's a **tunnel** that forwards to the real `smsonlin_vasa`
  server. User `mitch_read` is read-only: `SELECT` works, `DELETE` gets rejected. Nice guardrail.
- **Session** (`MySQLSession()` from `sessionmaker`) = one phone call. `with MySQLSession() as s:`
  borrows a connection from the pool and hangs up automatically when the block ends, even on error.
- **`text("SELECT ... WHERE hotel = :hotel")` + a params dict** = a *bound-parameter* query.
  SQLAlchemy sends the SQL and the values separately; MySQL slots the values in as pure data.
  This matters here more than usual: tool inputs are written by the model from **customer text**.
  A customer typing `doble'; DROP TABLE...` never becomes SQL. Never build SQL with f-strings.

So "how does a query connect to MySQL?" — you never connect manually. You open a session,
hand it `text()` SQL + params, and the engine does connection pooling under the hood.

## Step 0 — Discover the schema (you run this, read-only)

Nobody knows the table/column names yet — no .sql files in the repo. From
`/home/ubuntu/chatbot/backend` (cwd matters: config reads `.env` there):

```
uv run python
```

```python
from sqlalchemy import text
from app.database import MySQLSession

with MySQLSession() as s:
    for (t,) in s.execute(text("SHOW TABLES")):
        print(t)
```

Then for each candidate table (names like availability/rates/rooms/tarifas/disponibilidad):

```python
with MySQLSession() as s:
    for row in s.execute(text("DESCRIBE nombre_tabla")):
        print(row)
    for row in s.execute(text("SELECT * FROM nombre_tabla LIMIT 5")):
        print(row)
```

You're hunting for:
1. The **availability** table — hotel column, room-type column, a date column, a free-rooms count.
2. The **rates** table — is the price one flat number per room, or per-date (seasonal)?
3. The **exact string values** for hotels and room types (is it `antigua` or `Hotel Antigua`?
   `doble` or `Habitación Doble`?). These go into the tool enums later.

## Lesson 2 — How "seeing an opening" works

Typical hotel schema: **one row per (hotel, room type, date)** with a count of free rooms.
A stay Jul 20 → Jul 22 means the guest sleeps the nights of the 20th and 21st — checkout day
is NOT slept. So you query the **half-open range** `[check_in, check_out)`:

- `nights = (check_out - check_in).days` → 2
- Fetch rows `WHERE fecha >= check_in AND fecha < check_out`
- Available ⇔ you got exactly `nights` rows back **and** every free-count > 0.
  (Fewer rows than nights = some date missing from the table = can't confirm = not available.)

## Step 1 — Query functions in `app/queries.py` (you type)

Add imports at the top: `import json`, `from datetime import date`, and add `text` to the
existing sqlalchemy import. Then append (table/column names are PLACEHOLDERS until Step 0):

```python
def _parse_dates(check_in: str, check_out: str) -> tuple[date, date]:
    ci = date.fromisoformat(check_in)   # raises ValueError on garbage — good, we catch it later
    co = date.fromisoformat(check_out)
    if co <= ci:
        raise ValueError("check_out must be after check_in")
    return ci, co


def check_availability(hotel: str, room: str, check_in: str, check_out: str) -> str:
    ci, co = _parse_dates(check_in, check_out)
    nights = (co - ci).days
    with MySQLSession() as session:
        rows = session.execute(
            text("""
                SELECT fecha, libres              -- PLACEHOLDER columns
                FROM disponibilidad               -- PLACEHOLDER table
                WHERE hotel = :hotel AND tipo = :room
                  AND fecha >= :ci AND fecha < :co
            """),
            {"hotel": hotel, "room": room, "ci": ci, "co": co},
        ).all()
    available = len(rows) == nights and all(free > 0 for _, free in rows)
    return json.dumps(
        {"available": available, "hotel": hotel, "room": room, "nights": nights},
        ensure_ascii=False,
    )


def get_quote(hotel: str, room: str, check_in: str, check_out: str) -> str:
    ci, co = _parse_dates(check_in, check_out)
    nights = (co - ci).days
    with MySQLSession() as session:
        rate = session.execute(
            text("""
                SELECT tarifa_usd                 -- PLACEHOLDER
                FROM tarifas                      -- PLACEHOLDER
                WHERE hotel = :hotel AND tipo = :room
            """),
            {"hotel": hotel, "room": room},
        ).scalar_one()                            # exactly one row or it raises — also good
    total_usd = float(rate) * nights
    return json.dumps(
        {"hotel": hotel, "room": room, "nights": nights,
         "total_usd": round(total_usd, 2), "total_gtq": round(total_usd * 7.5, 2)},
        ensure_ascii=False,
    )
```

Why these choices:
- **Return JSON strings, not prose.** A tool_result's content is text; giving the model
  structured JSON keeps it from misreading numbers. `ensure_ascii=False` keeps ñ/á readable.
- **Do the math in Python.** Your current tool description tells Haiku "multiply by 7.5" —
  small models botch arithmetic mid-sentence. Calculators compute; models narrate.
- If Step 0 reveals **seasonal** (per-date) rates, sum the per-date rates over the range
  instead of `rate * nights`.

## Step 2 — The dispatcher in `app/main/tools.py` (you type)

Claude only names the tool; something must map that name to your Python function. Append:

```python
from app import queries


def process_tool_call(block) -> dict:
    try:
        if block.name == "check_availability":
            result = queries.check_availability(**block.input)
        elif block.name == "get_quote":
            result = queries.get_quote(**block.input)
        else:
            raise ValueError(f"Unknown tool: {block.name}")
        return {"type": "tool_result", "tool_use_id": block.id, "content": result}
    except Exception as e:
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"Error: {e}",
            "is_error": True,
        }
```

Concepts:
- **`tool_use_id`** pairs your answer with Claude's request — if Claude asked for two tools at
  once, the IDs are how it knows which result is which.
- **`is_error: True`** is the graceful path: instead of your server 500ing when the tunnel is
  down or the model sends a bad date, Claude *sees* the error and apologizes / asks the customer
  to rephrase. Errors become conversation, not crashes.
- **`**block.input`** unpacks Claude's JSON arguments straight into your function's keyword args
  — which works because your `input_schema` and your function signature use the same names.

Also edit the TOOLS descriptions while you're in there:
1. Both date fields: append "in YYYY-MM-DD format." (that's what `fromisoformat` parses).
2. Delete the "multiply by 7.5" sentence from `get_quote` — the tool computes GTQ now.
3. After Step 0: give `room` an `"enum": [...]` with the DB's exact strings, like `hotel` has.
   An enum stops the model guessing "doble matrimonial" when the DB says "DBL".

## Step 3 — The agentic loop in `app/main/chatbot.py` (you type)

Replace the body of `generate_response`:

```python
MAX_TOOL_ITERATIONS = 10   # module-level constant, near System_Prompt

    def generate_response(self, messages_user: list, max_tokens: int) -> str:
        messages = list(messages_user)          # copy: don't mutate the caller's history

        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.anthropic_Amanda.messages.create(
                model="claude-haiku-4-5",
                system=System_Prompt,
                max_tokens=max_tokens,
                messages=messages,
                tools=TOOLS,
            )
            if response.stop_reason != "tool_use":
                break                            # Claude gave a real answer — done looping

            messages.append({"role": "assistant", "content": response.content})
            tool_results = [
                process_tool_call(block)
                for block in response.content
                if block.type == "tool_use"
            ]
            messages.append({"role": "user", "content": tool_results})

        for block in response.content:
            if block.type == "text":
                return block.text
        return "Disculpe, tuve un problema al completar la consulta. Un asesor le apoyará en breve."
```

(And add `process_tool_call` to the import from `app.main.tools`.)

Line-by-line concepts:
- **`messages = list(messages_user)`** — the loop grows the list with tool traffic. Copying means
  routes.py still saves only what it always saved: the user's text + your return value. The tool
  back-and-forth stays in RAM, never in Postgres. That's why routes.py needs ZERO changes.
- **`messages.append({"role": "assistant", "content": response.content})`** — you append Claude's
  content blocks *verbatim*, tool_use blocks included. The API requires seeing its own request
  before your result, or it errors.
- **All tool_results in ONE user message** — if Claude requested 2 tools in parallel, both results
  go in a single `user` turn. Two separate user messages would break the pairing.
- **The cap (10)** — a confused model could request tools forever; the cap turns "infinite loop
  billing you per call" into a polite Spanish fallback.
- The final `for` replaces `"No response"`: extract the text block, or fall back gracefully.

## Step 4 — Clean the poisoned history (Postgres, review then delete)

Old conversations contain assistant rows saying "Claude wants to use the tool: ..." (and
`"No response"`). Those teach the model bad behavior by example. In a REPL / psql: SELECT the
`messages` rows where `role='assistant' AND message LIKE '%Claude wants to use the tool%'`,
eyeball them, then DELETE them (same for `'No response'`). Leftover back-to-back user turns are
fine — the API merges consecutive same-role messages.

## Step 5 — Verify end to end

1. REPL: call `queries.check_availability(...)` with a hotel/room/date combo you SAW in Step 0
   sample rows. Then a bad date → expect ValueError (the dispatcher will turn that into is_error).
2. Start the API from the backend dir: `uv run fastapi dev main.py` (cwd matters — `prompt.md`
   is a relative path).
3. `curl` POST /chat with a fresh UUID: ask availability in Spanish → expect a grounded sentence,
   not a stub. Follow up "¿Y cuánto me costaría?" → expect a quote with GTQ.
4. Check Postgres: only user text + final assistant text stored.
5. Load the chat page and repeat.

## Edge cases already accounted for

- Tunnel down / DB error → `is_error` tool_result → model apologizes instead of 500.
- Model doesn't know today's date → if "el próximo fin de semana" misfires, append
  `f"\nFecha de hoy: {date.today()}"` to the system prompt inside generate_response.
- Room name mismatches → fixed by the enum after Step 0.
- Known separate bug, NOT this pass: routes.py crashes on `UUID(None)` when the frontend omits
  `conversation_id`.