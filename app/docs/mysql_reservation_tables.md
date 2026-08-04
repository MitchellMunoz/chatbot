# MySQL reservation tables

in pasante table, tipodoc is useless. -mitch
the junto column is the concat of Compañia, numcon y letra - Mitch


Every table and column used to send a quote, charge a card, or make a reservation, with
its datatype and keys. Anything empty or dead is left out.

The join key is `SOLICITUD`. Never join on `boleta`.

```
bita2          SOLICITUD (PK)     quote / request + payment
  ├─ bita_reserva.SOLICITUD       confirmed reservation
  ├─ resecut.bitacora             points ledger
  ├─ allotment.bitacora           unit consumed
  ├─ comen.bitacora               notes + charge log
  └─ saldofav.bitacora            credit balance movement
```

**None of these joins is a declared foreign key.** The schema has no FK constraints on
any reservation table — every relationship above is convention only. `resecut.bitacora`
and `allotment.bitacora` are not even indexed.

## Which tables each flow touches

| flow | tables |
|---|---|
| send a quote | `bita2` · `canual` · `condir` · `tarifa_hotel3` · `tasa` · `destino` · `tipo_unid` · `combinaciones` · `temp_combinaciones` · `allotment` · `allotnoc` · `allotnocb` · `solicitudes_allotment` · `detalle_soli_allotment` · `pasante` · `bono_otorgado` · `junto_pendiente_actualizar` · `emergente` |
| charge a card | `credit_cards` · `credit_cards_log` · `issuing_bank` · `bin_list_tarjetas` · `bin_list_tarjetas_gua` · `bin_cache` · `network` · `type_acquiring` · `tipo_tarjeta` · `forma_pago` · `saldofav` · `comen` |
| make a reservation | `bita_reserva` · `bita_reserva_audit` · `resecut` · `allotment` · `destino` · `distribucion` · `vencimiento_detalle` · `saldofav` · `bono_otorgado` · `boletas_eliminadas` · `comen` · `sec_4users` |

## The write path is stored procedures

**Nothing writes these tables directly.** The form calls stored procedures, and there are
49 of them in the schema. Reimplementing the flows in Postgres means reimplementing
these — a table-level copy will not reproduce the behaviour.

| procedure | writes | reads |
|---|---|---|
| `crearBitacora` | `bita2` | `canual` `condir` `pasante` `bono_otorgado` `tasa` |
| `CERRAR_BITACORAS` | `bita2` | |
| `llenar_temp_combinaciones` | `temp_combinaciones` | `allotment` `tipo_unid` |
| `crearReserva` | `bita_reserva` `saldofav` | `bita2` `allotment` `sec_4users` |
| `ELIMINAR_RESERVA` | `allotment` `bita_reserva` `comen` `resecut` `saldofav` | `pasante` |
| `CANCELACION_RESERVA_CON_SALDO_A_FAVOR` | `allotment` `bita_reserva` `comen` `resecut` `saldofav` | `bita2` `pasante` |
| `RESERVA_CON_SALDO_A_FAVOR` | `comen` `saldofav` | `bita2` `bita_reserva` `pasante` |
| `PASAR_DE_R_A_U_RESERVAS` | `bita2` `bita_reserva` `destino` `pasante` `resecut` | |
| `RESERVA_USANDO_PUNTOS_LIBERADOS_AI` | `resecut` `vencimiento_detalle` | |
| `RECORRER_RESERVA` / `USODEPUNTOS2` | `distribucion` | `pasante` `resecut` |
| `crear_tarjeta_credito` | `credit_cards` `issuing_bank` | `bin_list_tarjetas` |
| `actualizar_tarjetas_credito` | | `credit_cards` `pasante` |
| `actualizarCuenta` | `pasante` | `canual` `resecut` `saldofav` `bono_otorgado` |
| `allotment_ano` / `allotment_mes` | `allotnocg` `allotnocr` | `allotnoc` `allotnocb` |

`crear_tarjeta_credito` does `INSERT IGNORE INTO issuing_bank` before inserting the card,
so the issuer list grows itself from whatever the agent types.

There are **no triggers** in this schema. Anything that looks trigger-maintained,
including `bita_reserva_audit`, is written by application code or one of these
procedures.

## Contents

- [bita2](#bita2) — quote
- [tarifa_hotel3](#tarifa_hotel3) — points rate
- [tasa](#tasa) — exchange rate
- [bita_reserva](#bita_reserva) — reservation
- [bita_reserva_audit](#bita_reserva_audit)
- [resecut](#resecut) — points ledger
- [boletas_eliminadas](#boletas_eliminadas)
- [comen](#comen) — notes and charges
- [pasante](#pasante) — member
- [junto_pendiente_actualizar](#junto_pendiente_actualizar)
- [emergente](#emergente)
- [allotment](#allotment) — inventory
- [solicitudes_allotment](#solicitudes_allotment) — inventory request
- [bono_otorgado](#bono_otorgado)
- [saldofav](#saldofav) — credit balance
- [credit_cards](#credit_cards) — cards on file
- [credit_cards_log](#credit_cards_log)
- [Card lookups](#card-lookups)
- [Lookup tables](#lookup-tables)
- [Coded values](#coded-values)
- [Legacy card columns](#legacy-card-columns)
- [Postgres contracts](#postgres-contracts) — how contracts was filled

## bita2

One row per quote, booked or not. `SOLICITUD` is the Bitácora No the agent sees — MySQL
assigns it via `auto_increment`, the form does not supply it. Next value 325096, and the
range 122503–325095 across 92,823 rows is sparse.

### Identity and audit

| table | column | type | key | note |
|---|---|---|---|---|
| `bita2` | `SOLICITUD` | `int` | PK, auto_inc | the Bitácora No |
| `bita2` | `JUNTO` | `varchar(7)` | index | membership number |
| `bita2` | `FECHA` | `date` | index | date quoted |
| `bita2` | `HORA` | `varchar(8)` | | `HH:MM:SS` on all rows |
| `bita2` | `USUARIO` | `varchar(20)` | index | agent who opened it, 44 distinct |
| `bita2` | `USUARIOULT` | `varchar(20)` | | agent who last touched it |
| `bita2` | `FECHA_ACTU` | `timestamp` | | last update |
| `bita2` | `REFIERE` | `varchar(8)` | | referral |

### Outcome and channel

| table | column | type | key | note |
|---|---|---|---|---|
| `bita2` | `RESULTADO` | `varchar(16)` | index | the booked flag |
| `bita2` | `ESTATUS` | `varchar(9)` | | workflow state, independent of `RESULTADO` |
| `bita2` | `TIPOSOL` | `varchar(15)` | | the channel, labelled Medio on the form; values from `tipo_sol` |
| `bita2` | `ASUNTO` | `varchar(15)` | | labelled Tipo Reserva; values from `tipo_reserva` |
| `bita2` | `SOLUCION` | `varchar(10)` | | `SOLIRES` on every completed quote |

`RESULTADO = 'confirmada'` is what actually means booked: those rows have a
`bita_reserva` row almost always, `Informacion` rows almost never, `No hay espacios` and
`Lista de Espera` never. It is independent of `ESTATUS` — `confirmada` + `pendiente`
occurs on about 750 rows.

### Contact and billing identity

| table | column | type | key | note |
|---|---|---|---|---|
| `bita2` | `NOMBRERES` | `varchar(40)` | | guest name |
| `bita2` | `TELEFONO` | `varchar(12)` | | phone |
| `bita2` | `FAX` | `varchar(11)` | | not a fax — a second phone |
| `bita2` | `MAIL` | `varchar(45)` | | email |
| `bita2` | `NIT` | `varchar(10)` | | tax id, not numeric |
| `bita2` | `NITNOMBRE` | `varchar(40)` | | billing name |
| `bita2` | `HABLADO` | `varchar(40)` | | who was spoken to |

### Room blocks

A quote carries up to three room blocks in parallel column families, distinguished by a
numeric suffix. Block 1 is on every quote, block 2 on about a tenth, block 3 rarely. All
of these live in `bita2`.

| table | role | block 1 | block 2 | block 3 | type |
|---|---|---|---|---|---|
| `bita2` | hotel | `HOTEL1` | — | — | `int`, indexed |
| `bita2` | check-in | `FECHADEL1` | `FECHADEL2` | `FECHADEL3` | `date` |
| `bita2` | check-out | `FECHASAL1` | `FECHAAL2` | `FECHAAL3` | `date` |
| `bita2` | adults | `ADULTOS` | `ADULTOS2` | `ADULTOS3` | `varchar(2)` |
| `bita2` | children | `NINOS` | `NINOS2` | `NINOS3` | `varchar(2)`, `NINOS3` is `varchar(1)` |
| `bita2` | room code | `HABITA1` | `HABITA2` | `HABITA3` | `varchar(20)`, `HABITA3` is `varchar(19)` |
| `bita2` | unit count | `unidad1` | `unidad2` | `unidad3` | `int` |
| `bita2` | season | `destino1` | `destino2` | `destino3` | `varchar(10)` |
| `bita2` | season alt | `destino11` | `destino22` | `destino33` | `varchar(10)` |
| `bita2` | nights | `noches1` | `noches2` | `noches3` | `int` |
| `bita2` | nights alt | `noches11` | `noches22` | `noches33` | `int` |
| `bita2` | points | `punto` | `punto2` | `punto3` | `decimal(6,2)` |
| `bita2` | maint. points | — | `manto_pts2` | `manto_pts3` | `decimal(6,1)` |
| `bita2` | maint. amount | — | `manto_pts2_d` | `manto_pts3_d` | `decimal(12,2)` |
| `bita2` | reservation type | `TIPO_RESERVA` | — | — | `varchar(100)` |

Consider normalising these into a child table with one row per block rather than
carrying 39 columns across.

Four traps in that family:

`HABITA1` holds the room code, not a description — `D2DL` `B2BR` `STL` `B1BR` `V1BR`
`D2JSE` `PROS` `OTROS`. Same pre-split codes as `resecut.CVEUNI`, so `D2DL` needs
resolving to `D2DLA` / `D2DLP` by hotel, exactly like the allotments backfill.

`unidad1` is the number of units (1–7), not a room id.

`ADULTOS` and `NINOS` are `varchar`, not ints, though every value parses as a number
(max 80). An unused block stores `''` or `'0'`, never `NULL` — so treat blank as absent,
or a block-2 row appears with 0 adults instead of not existing.

`TIPO_RESERVA2`, `TIPO_RESERVA3` and `TIPO_RESERVA4` exist and are nearly always
populated, but each is a copy of `TIPO_RESERVA` written on every row regardless of how
many blocks the quote has. No per-block information. There is also a fourth block
(`fechadel4`, `habita4`, `punto4`, `noches4`, `destino4`, `unidad4`, `manto_pts4`) that
is entirely empty — what looks like data in `adultos4` and `ninos4` is the literal
string `'0'`.

### Points and money

| table | column | type | key | note |
|---|---|---|---|---|
| `bita2` | `PUNLOC` | `decimal(6,1)` | | local points |
| `bita2` | `PUNDIS` | `decimal(13,1)` | | points available at quote time |
| `bita2` | `BONODIS` | `decimal(8,1)` | | bonus available at quote time |
| `bita2` | `DIFPUNINT` | `decimal(10,2)` | | points difference |
| `bita2` | `TOTAL` | `decimal(10,2)` | | USD, −1188 to 11884 — negatives exist |
| `bita2` | `TOTALQ` | `decimal(10,2)` | | quetzales, −6014.92 to 92814.04 |
| `bita2` | `TCAMBIO` | `decimal(10,2)` | | rate used; max 297.50 is garbage against a real rate near 7.62 |
| `bita2` | `MANTOPUNTO` | `decimal(10,2)` | | points maintenance fee |
| `bita2` | `CUOTAANUAL` | `decimal(10,2)` | | annual fee |
| `bita2` | `CUOTAMEM` | `decimal(10,2)` | | membership fee |
| `bita2` | `saldofav` | `decimal(12,2)` | | credit balance applied |
| `bita2` | `FECHA_PAGO` | `date` | | payment date, 224 zero dates |

`TOTAL = 360.00` with `TCAMBIO = 7.62` gives `TOTALQ = 2743.20`, so the three are
consistent where the rate is sane.

### Guest surcharge and payment reference

| table | column | type | key | note |
|---|---|---|---|---|
| `bita2` | `INVITADO` | `tinyint(1)` | | 0/1 flag |
| `bita2` | `TOTAL_INV` | `decimal(14,2)` | | the amount, set on 2,220 of the 2,238 flagged rows |
| `bita2` | `CHEQUENO` | `varchar(45)` | | cheque ref |
| `bita2` | `CHEQUEBCO` | `varchar(20)` | | cheque bank |
| `bita2` | `DEPOSITONO` | `varchar(10)` | | deposit ref |
| `bita2` | `DEPOSITOBC` | `varchar(10)` | | deposit bank |

The card columns on `bita2` are legacy duplicates of `credit_cards` — see
[Legacy card columns](#legacy-card-columns).

## tarifa_hotel3 ### ignore this table... its not needed... we use calendar and hotel rates


## tasa

The daily USD/GTQ rate, one row per day, currently to 2026-07-31. This is the source for
`bita2.TCAMBIO` and is what `app/cron_jobs/sync_exchange_rate.py` maintains.

| table | column | type | key | note |
|---|---|---|---|---|
| `tasa` | `corr` | `int` | PK, auto_inc | |
| `tasa` | `fecha` | `date` | index | one row per day |
| `tasa` | `tasa` | `decimal(6,2)` | | rate |

## bita_reserva

One row per booking. `boleta` is the number the member is told — also `auto_increment`
(next 302833), also not supplied by the form.

| table | column | type | key | note |
|---|---|---|---|---|
| `bita_reserva` | `boleta` | `int` | PK, auto_inc | the member-facing number |
| `bita_reserva` | `SOLICITUD` | `int` | join → `bita2`, indexed | the join |
| `bita_reserva` | `JUNTO` | `varchar(7)` | index | membership number |
| `bita_reserva` | `FECHA` | `date` | index | booked on — use this, not `feccon` |
| `bita_reserva` | `FECHASOL` | `date` | | date of the original quote |
| `bita_reserva` | `HOTEL1` | `int` | index | hotel |
| `bita_reserva` | `FECHADEL1` | `date` | index | check-in |
| `bita_reserva` | `FECHASAL1` | `date` | | check-out |
| `bita_reserva` | `ADULTOS` | `varchar(2)` | | text, not int |
| `bita_reserva` | `NINOS` | `varchar(2)` | | text, not int |
| `bita_reserva` | `noches` | `int` | | nights quoted |
| `bita_reserva` | `noches_real` | `int` | | nights actually stayed |
| `bita_reserva` | `tipo_habita` | `varchar(70)` | | free text (`1 BÚNGALO DE 4`), not a room code |
| `bita_reserva` | `habita_real` | `text` | | room actually given |
| `bita_reserva` | `puntos_reserva` | `decimal(7,1)` | | points charged |
| `bita_reserva` | `NOMBRERES` | `varchar(40)` | | guest |
| `bita_reserva` | `TELEFONO` | `varchar(12)` | | phone |
| `bita_reserva` | `MAIL` | `varchar(45)` | | email |
| `bita_reserva` | `ESTATUS` | `varchar(50)` | index | `UTILIZADA` / `CANCELADO` — different vocabulary from `bita2.ESTATUS` |
| `bita_reserva` | `ASUNTO` | `varchar(25)` | | reservation type |
| `bita_reserva` | `confirmahotel` | `varchar(20)` | | hotel confirmation code |
| `bita_reserva` | `confirmas` | `varchar(80)` | | second confirmation code |
| `bita_reserva` | `observa` | `text` | | notes |
| `bita_reserva` | `USUARIO` | `varchar(20)` | index | agent |
| `bita_reserva` | `USUARIOULT` | `varchar(8)` | | last agent |

`feccon` is `0000-00-00` on all 51,080 rows and `HORA` is blank on every row — both look
useful and hold nothing.

## bita_reserva_audit

A trigger-written audit trail, one row per change, 51,128 rows and current to today.

| table | column | type | key | note |
|---|---|---|---|---|
| `bita_reserva_audit` | `id` | `bigint` | PK, auto_inc | |
| `bita_reserva_audit` | `boleta` | `int` | index → `bita_reserva` | which reservation |
| `bita_reserva_audit` | `changed_column` | `varchar(64)` | | **always `usuario`** |
| `bita_reserva_audit` | `new_value` | `text` | | the new value |
| `bita_reserva_audit` | `changed_by` | `varchar(100)` | | MySQL user |
| `bita_reserva_audit` | `changed_at` | `datetime` | index | when |
| `bita_reserva_audit` | `change_type` | `varchar(10)` | | operation |
| `bita_reserva_audit` | `connection_id` | `int` | | MySQL connection |

Worth knowing before you rely on it: `changed_column` is `usuario` on all 51,128 rows, so
the trigger only tracks that one column. `old_value` is populated on 0.1% of rows and
`extra_info` is empty, so you cannot reconstruct a before/after history from this table.

## resecut

One to six rows per reservation. The only table that carries the room code on the booked
side.

| table | column | type | key | note |
|---|---|---|---|---|
| `resecut` | `CORR` | `int` | PK, auto_inc | |
| `resecut` | `bitacora` | `int` | join → `bita2`, **not indexed** | the join, not named `SOLICITUD` |
| `resecut` | `BOLETA` | `varchar(7)` | index | reservation number, text |
| `resecut` | `JUNTO` | `varchar(7)` | index | membership number |
| `resecut` | `CVEUNI` | `varchar(10)` | | room code, pre-split `D2DL` |
| `resecut` | `NUMPUN` | `decimal(10,1)` | | points on this line |
| `resecut` | `cant_uni` | `int` | | units of this room type |
| `resecut` | `noc_fin` | `int` | | weekend nights |
| `resecut` | `noc_entre` | `int` | | weekday nights |
| `resecut` | `NUMSEM` | `int` | | week number |
| `resecut` | `SEMNOC` | `int` | | weeks/nights flag |
| `resecut` | `destino_res` | `varchar(12)` | | season code, e.g. `20261023` |
| `resecut` | `FECDIA` | `date` | index | 32 zero dates |
| `resecut` | `FECTRA` | `date` | | transaction date |
| `resecut` | `PERIODO` | `varchar(7)` | | period |
| `resecut` | `NUMCON` | `int` | | contract |
| `resecut` | `NUMANO` | `int` | | contract year |
| `resecut` | `SECPUN` | `int` | index | sequence |
| `resecut` | `FE` | `varchar(2)` | | |
| `resecut` | `TIPDOC` | `varchar(3)` | | document type |
| `resecut` | `nor_bono` | `varchar(12)` | index | points / bonus / certificate |
| `resecut` | `CUESTA` | `varchar(2)` | index | used / cancelled / returned |
| `resecut` | `TIPCAN` | `varchar(2)` | | cancellation reason |
| `resecut` | `DESUSO` | `varchar(20)` | | usage note |
| `resecut` | `desdoc` | `varchar(60)` | | document description |
| `resecut` | `certi` | `varchar(20)` | | certificate ref |
| `resecut` | `nconfir` | `varchar(80)` | | confirmation number |
| `resecut` | `FACTURA` | `varchar(20)` | | invoice |
| `resecut` | `LOCALINTER` | `varchar(5)` | | local / international |
| `resecut` | `impcuo` | `decimal(12,2)` | | amount due |
| `resecut` | `imppag` | `decimal(12,2)` | | amount paid |
| `resecut` | `NOMBRE1` | `varchar(40)` | | member name |

`CVEUNI` carries the shared `D2DL`; our `room_types` splits it into `D2DLA` / `D2DLP`.
Resolve by hotel, same as the allotments backfill.

## boletas_eliminadas

Deleted reservations, kept out of `resecut` so the points ledger stays clean. 452 rows,
most recent 2026-07-23. Same shape as `resecut` plus who deleted it.

| table | column | type | key | note |
|---|---|---|---|---|
| `boletas_eliminadas` | `CORR` | `int` | PK, auto_inc | |
| `boletas_eliminadas` | `bitacora` | `int` | join → `bita2` | the quote |
| `boletas_eliminadas` | `BOLETA` | `varchar(7)` | | the deleted reservation |
| `boletas_eliminadas` | `JUNTO` | `varchar(7)` | | membership number |
| `boletas_eliminadas` | `NOMBRE1` | `varchar(40)` | | member name |
| `boletas_eliminadas` | `CVEUNI` | `varchar(10)` | | room code |
| `boletas_eliminadas` | `cant_uni` | `int` | | units |
| `boletas_eliminadas` | `NUMPUN` | `decimal(10,1)` | | points |
| `boletas_eliminadas` | `impcuo` | `decimal(12,2)` | | amount due |
| `boletas_eliminadas` | `FECDIA` | `date` | | ledger date |
| `boletas_eliminadas` | `FECTRA` | `date` | | transaction date |
| `boletas_eliminadas` | `NUMCON` | `int` | | contract |
| `boletas_eliminadas` | `NUMANO` | `int` | | contract year |
| `boletas_eliminadas` | `SECPUN` | `int` | | sequence |
| `boletas_eliminadas` | `SEMNOC` | `int` | | weeks/nights flag |
| `boletas_eliminadas` | `NUMSEM` | `int` | | week number |
| `boletas_eliminadas` | `TIPDOC` | `varchar(3)` | | document type |
| `boletas_eliminadas` | `nor_bono` | `varchar(10)` | | points / bonus / certificate |
| `boletas_eliminadas` | `CUESTA` | `varchar(2)` | | state |
| `boletas_eliminadas` | `DESUSO` | `varchar(20)` | | usage note |
| `boletas_eliminadas` | `nconfir` | `varchar(80)` | | confirmation number |
| `boletas_eliminadas` | `FE` | `varchar(2)` | | |
| `boletas_eliminadas` | `usuario_borra` | `varchar(10)` | | who deleted it |
| `boletas_eliminadas` | `fecha_borra` | `datetime` | | when |

## comen

Where every interaction and every card charge is written, in prose.

| table | column | type | key | note |
|---|---|---|---|---|
| `comen` | `CORR` | `int` | PK, auto_inc | |
| `comen` | `bitacora` | `int` | join → `bita2`, indexed | the join |
| `comen` | `JUNTO` | `varchar(10)` | index | membership number |
| `comen` | `CARACTERN` | `int` | index | `JUNTO` as an int, prefix stripped (`914932R` → `14932`); most indexes use it |
| `comen` | `FECHA` | `date` | index | |
| `comen` | `HORA` | `varchar(20)` | index | dirty — 561 rows are `HH:MM`, 3 hold junk like `926580` |
| `comen` | `USUARIO` | `varchar(20)` | index | agent |
| `comen` | `GRUPO` | `varchar(10)` | index | department |
| `comen` | `TIPOCOM` | `varchar(40)` | index | note type |
| `comen` | `ESTATUS` | `varchar(10)` | | state |
| `comen` | `COMENTA` | `text` | | the note |
| `comen` | `COMENTA2` | `text` | | overflow |
| `comen` | `COMENTA3` | `text` | | overflow |
| `comen` | `COMENTA4` | `text` | | overflow |
| `comen` | `COMENTA5` | `text` | | overflow — a long note continues across all five |

`GRUPO = 'COBROS'` with `TIPOCOM = 'RECURRENTE'` and text like
`CARGO 3 CM A TC. REGISTRADA` marks a recurring card charge run by hand.

**Nothing in MySQL records a charge authorization.** There is no auth code, approval
code, transaction id or gateway response anywhere in the schema. A `transaccion_pago`
table exists with `id_transaccion`, `monto`, `ultimos_cuatro_digitos` and a
`pasarela` enum of `fac` / `cyber`, but it has **0 rows**, as do `reserva_habitacion` and
`reserva_evento` which reference it. So `comen` prose remains the only evidence that a
charge happened or worked.

## pasante

38,774 rows, 7,662 of them active. Active means `TIPCAN` is empty; any value is a
cancellation reason.

| table | column | type | key | note |
|---|---|---|---|---|
| `pasante` | `CORR` | `int` | PK, auto_inc | |
| `pasante` | `JUNTO` | `varchar(7)` | index, **not unique** | the key used everywhere |
| `pasante` | `NUMCON` | `int` | index | contract |
| `pasante` | `NOMBRE1` | `varchar(40)` | index | primary name |
| `pasante` | `NOMBRE2` | `varchar(40)` | index | secondary name |
| `pasante` | `ESTATUS` | `varchar(10)` | | `ACTIVO` |
| `pasante` | `TIPCAN` | `varchar(2)` | index | empty = active |
| `pasante` | `programa` | `varchar(10)` | | `INHOPA`, `PENDIN`, … |
| `pasante` | `PUNTOS_DISPONIBLES` | `int` | | stale — see `junto_pendiente_actualizar` |
| `pasante` | `PUNTOS_PAGADOS` | `int` | | points paid for |
| `pasante` | `saldofav` | `decimal(10,2)` | | credit balance |
| `pasante` | `FECCON` | `date` | index | contract date |
| `pasante` | `fecven` | `date` | index | contract expiry |
| `pasante` | `fecnac` | `date` | | date of birth |
| `pasante` | `MAIL` | `varchar(60)` | | email |
| `pasante` | `telcas` | `varchar(20)` | | home phone |
| `pasante` | `telofi` | `varchar(20)` | | office phone |
| `pasante` | `DPI` | `varchar(20)` | | national id |
| `pasante` | `NIT` | `varchar(20)` | | tax id |
| `pasante` | `nitnombre` | `varchar(50)` | | billing name |
| `pasante` | `DIREC` | `varchar(90)` | | address |
| `pasante` | `codpos` | `varchar(8)` | | postal code |

### TIPCAN and ESTATUS are trying to do the same thing

Both encode whether a contract is alive, and that one bit is stored twice. Derive
`ESTATUS` from `TIPCAN` with three rules — empty means alive, `CV` or `AM` means
`VENCIDO`, anything else means `INACTIVO` — and 38,329 of 38,774 rows come out right.
98.9%. The 445 that disagree are drift, not meaning.

Past that shared bit, each column knows one thing the other cannot represent.

`TIPCAN` cannot see the `ACTIVO` / `SUSPENDIDO` split. Both are `''`. That is 1,271
contracts, in term but frozen for non-payment, that `TIPCAN` calls alive and `ESTATUS`
does not.

`ESTATUS` cannot see the reason. `INACTIVO` collapses 53 distinct `TIPCAN` codes into
one value.

| `ESTATUS` | rows | in term | avg % paid | avg missed | distinct `TIPCAN` |
|---|---|---|---|---|---|
| `INACTIVO` | 20,504 | 5,015 | 159.0 | 20.98 | 53 |
| `VENCIDO` | 10,591 | 184 | 232.1 | 13.93 | 6 |
| `ACTIVO` | 6,408 | 6,325 | 117.2 | 4.01 | 4 |
| `SUSPENDIDO` | 1,271 | 1,252 | 35.0 | 36.83 | 1 |

So the two counts of "active" differ: `TIPCAN = ''` gives 7,662, `ESTATUS = 'ACTIVO'`
gives 6,408, and they agree on 6,390. `TIPCAN` over-counts by 1,272 and under-counts by
18.

Nothing keeps them in step. `vencerContratosMes` is the only procedure that writes
`pasante.ESTATUS`, and it keys on `TIPCAN` alone — `WHERE TIPCAN = 'PD'` sets
`INACTIVO`, `WHERE TIPCAN = ' ' OR TIPCAN = 'SC'` sets `VENCIDO` — never reading
`ESTATUS` before overwriting it. No procedure anywhere contains the string
`SUSPENDIDO`, so the PHP layer sets that state without touching `TIPCAN`, and the
expiry job stays blind to it.

The reader compensates by requiring both. `actualizarCuentaTodosLosContratos` selects
`WHERE TIPCAN = '' AND PEPE > 0 AND ESTATUS = 'ACTIVO'`, which is the intersection —
6,390 rows, narrowing to 3,789 once `PEPE > 0` applies. That contains the drift instead
of preventing it: 1,281 contracts that still owe installments are skipped from balance
recalculation because the two columns disagree about them. The failure mode is omission,
never processing a dead contract.

Treat `ESTATUS` as the state and `TIPCAN` as the exit reason. An active flag should come
from `ESTATUS = 'ACTIVO'`, not from `TIPCAN` being empty. The `empty = active` claim
earlier in this file counts the 1,271 `SUSPENDIDO` contracts as active.

## junto_pendiente_actualizar

The queue behind `actualizarCuenta(junto)`. 20,741 rows and written continuously — a
member lands here when their points balance is stale, which is why
`pasante.PUNTOS_DISPONIBLES` cannot be trusted for a quote.

| table | column | type | key | note |
|---|---|---|---|---|
| `junto_pendiente_actualizar` | `id` | `int` | PK, auto_inc | |
| `junto_pendiente_actualizar` | `junto` | `varchar(10)` | | membership number |
| `junto_pendiente_actualizar` | `estatus` | `enum` | | `pendiente` / `actualizado` |
| `junto_pendiente_actualizar` | `fecha` | `datetime` | | queued at |

## emergente

Pop-up alerts shown to the agent when a member's account is opened. 13,254 rows, current.

| table | column | type | key | note |
|---|---|---|---|---|
| `emergente` | `corr` | `int` | PK, auto_inc | |
| `emergente` | `junto` | `varchar(7)` | index | membership number |
| `emergente` | `emergente` | `text` | | the alert text |
| `emergente` | `activa` | `varchar(8)` | | whether it still shows |
| `emergente` | `grupo` | `varchar(20)` | | department |
| `emergente` | `fecha` | `date` | | |
| `emergente` | `hora` | `varchar(20)` | | |
| `emergente` | `usuario` | `varchar(20)` | | who wrote it |

## allotment

Inventory. Already mapped in `app/mysql.py`.

| table | column | type | key | note |
|---|---|---|---|---|
| `allotment` | `corr` | `int` | PK, auto_inc | |
| `allotment` | `unidad` | `varchar(10)` | index | room code |
| `allotment` | `HOTEL` | `int` | index | 1 antigua, 2 pacifico; other values are separate properties |
| `allotment` | `entra` | `date` | index | check-in |
| `allotment` | `sale` | `date` | index | check-out |
| `allotment` | `estado` | `varchar(20)` | index | availability |
| `allotment` | `PTS` | `varchar(15)` | index | filter on `'pts'` |
| `allotment` | `JUNTO` | `varchar(7)` | | membership number |
| `allotment` | `NOMBRE` | `varchar(50)` | | guest |
| `allotment` | `bitacora` | `int` | join → `bita2`, **not indexed** | quote that consumed the unit |
| `allotment` | `reserva` | `int` | | reservation |
| `allotment` | `visible_web` | `varchar(2)` | | shown online |
| `allotment` | `MODIFICA` | `date` | | day resolution only, NULL on ~4,900 rows — cannot be the only watermark |
| `allotment` | `CREACION` | `date` | | created |
| `allotment` | `update_estado` | `timestamp` | | better watermark candidate |
| `allotment` | `CONFIRMA` | `varchar(60)` | index | confirmation |
| `allotment` | `observa` | `text` | | notes |
| `allotment` | `tipo` | `varchar(10)` | index | type |
| `allotment` | `numcon` | `int` | | contract |
| `allotment` | `id_solires` | `int` | | solires id |

`entra` and `sale` are declared `NOT NULL`. The comment in `app/mysql.py` says they hold
`0000-00-00`; on current data they do not — 67,736 rows, no zero dates, no nulls,
earliest `2021-10-01`. Nothing in MySQL prevents one reappearing.

## solicitudes_allotment

When inventory is not free, the agent raises a request and someone authorises it. Two
tables: the header and one row per unit/date asked for. 5,164 and 6,709 rows, both
written today.

| table | column | type | key | note |
|---|---|---|---|---|
| `solicitudes_allotment` | `id` | `int` | PK, auto_inc | |
| `solicitudes_allotment` | `hotel` | `int` | index | hotel |
| `solicitudes_allotment` | `unidad` | `int` | index | unit type |
| `solicitudes_allotment` | `cantidad` | `int` | | units wanted |
| `solicitudes_allotment` | `fecha_entrada` | `date` | | check-in |
| `solicitudes_allotment` | `fecha_salida` | `date` | | check-out |
| `solicitudes_allotment` | `estatus` | `enum` | | only `si_hay`, `denegada`, `pendiente` occur |
| `solicitudes_allotment` | `status_cp` | `enum` | | secondary state, set on 10% |
| `solicitudes_allotment` | `usuario_sol` | `varchar(50)` | index | who asked |
| `solicitudes_allotment` | `usuario_auto` | `varchar(50)` | index | who authorised |
| `solicitudes_allotment` | `fecha_respuesta` | `datetime` | | answered at |
| `solicitudes_allotment` | `contrato` | `varchar(100)` | | contract, on 43% |
| `solicitudes_allotment` | `porcentaje` | `decimal(10,2)` | | discount, on 11% |
| `solicitudes_allotment` | `nombre_reserva` | `varchar(200)` | | guest, on 5% |
| `solicitudes_allotment` | `comentario` | `text` | | |
| `solicitudes_allotment` | `created_at` | `timestamp` | | |
| `solicitudes_allotment` | `updated_at` | `timestamp` | | auto-updates |
| `detalle_soli_allotment` | `id` | `int` | PK, auto_inc | |
| `detalle_soli_allotment` | `id_solicitud` | `int` | index → `solicitudes_allotment.id` | the header |
| `detalle_soli_allotment` | `unidad` | `varchar(10)` | | room code — text here, `int` on the header |
| `detalle_soli_allotment` | `entra` | `date` | | check-in |
| `detalle_soli_allotment` | `sale` | `date` | | check-out |
| `detalle_soli_allotment` | `estatus` | `enum` | | per-line state |
| `detalle_soli_allotment` | `porcentaje` | `int` | | discount, on 13% |
| `detalle_soli_allotment` | `comentario` | `text` | | on 19% |
| `detalle_soli_allotment` | `created_at` | `timestamp` | | |
| `detalle_soli_allotment` | `updated_at` | `timestamp` | | auto-updates |

`unidad` is an `int` on the header and a `varchar(10)` room code on the detail — they are
not the same kind of value.

## bono_otorgado

Bonus points granted to a member, 31,232 rows, current.

| table | column | type | key | note |
|---|---|---|---|---|
| `bono_otorgado` | `CORR` | `int` | PK, auto_inc | |
| `bono_otorgado` | `JUNTO` | `varchar(7)` | index | membership number |
| `bono_otorgado` | `NUMPUN` | `decimal(7,2)` | | points granted |
| `bono_otorgado` | `tipo` | `varchar(10)` | | bonus type |
| `bono_otorgado` | `fecha` | `date` | | granted on |
| `bono_otorgado` | `observa` | `varchar(100)` | | reason |

**Bono points are 25% of purchased points.** The Bono Disponibles figure on the bitácora
is therefore a function of the contract, not an independent balance.

Which column is the denominator is unresolved. It is not `pasante.PUNTOS_PAGADOS`: across
4,839 active members with a positive `PUNTOS_PAGADOS`, only 19 have total granted bonus
equal to 25% of it, and the mean ratio is 1.77 rather than 0.25. Grouping grants by year
does not help either — 23 of 4,920 member-years match. The most common single-grant
ratios against `PUNTOS_PAGADOS` are exactly `1.00` (542 grants) and exactly `4.00` (398),
so the 25% may run the other way, or against a different base.

## saldofav

The credit-balance ledger, 15,422 rows, current. `pasante.saldofav` is the running total;
this is the movement detail, and it links back to both the quote and the reservation.

| table | column | type | key | note |
|---|---|---|---|---|
| `saldofav` | `CORR` | `int` | PK, auto_inc | |
| `saldofav` | `JUNTO` | `varchar(7)` | index | membership number |
| `saldofav` | `FECHA` | `datetime` | | when |
| `saldofav` | `CREDITO` | `decimal(12,2)` | | amount in |
| `saldofav` | `DEBITO` | `decimal(12,2)` | | amount out |
| `saldofav` | `DESCRIP` | `varchar(250)` | | description |
| `saldofav` | `motivo` | `varchar(15)` | | reason code, on 48% |
| `saldofav` | `bitacora` | `int` | index → `bita2` | the quote, on 46% |
| `saldofav` | `boleta` | `int` | → `bita_reserva` | the reservation, on 35% |
| `saldofav` | `USUARIO` | `varchar(30)` | | agent |

Every row has exactly one of `CREDITO` or `DEBITO`, never both.

## credit_cards

**The card-on-file store.** 39,763 cards covering 38,459 distinct members, written today,
and 39,760 of the rows match a `pasante` row. This is the live vault — the card columns
on `bita2` and `pasante` are the older duplicates.

| table | column | type | key | note |
|---|---|---|---|---|
| `credit_cards` | `corr` | `int` | PK, auto_inc | |
| `credit_cards` | `junto` | `varchar(33)` | index | membership number — `varchar(33)` where every other table uses 7 |
| `credit_cards` | `numero` | `varchar(25)` | | **card number in the clear**, on 93% |
| `credit_cards` | `nombre` | `varchar(100)` | | cardholder name |
| `credit_cards` | `vence_mes` | `int` | | expiry month, on 32% |
| `credit_cards` | `vence_ano` | `int` | | expiry year, on 32% |
| `credit_cards` | `forma_pago` | `varchar(100)` | index | `CRÉDITO` / `DÉBITO` / `DEPOSITO` |
| `credit_cards` | `network` | `varchar(100)` | index | card network, on 47% |
| `credit_cards` | `issuing_bank` | `varchar(100)` | index | issuer, on 90% |
| `credit_cards` | `es_principal` | `tinyint` | | the member's default card |
| `credit_cards` | `es_oficial` | `tinyint` | index | verified card |
| `credit_cards` | `created_at` | `datetime` | | |
| `credit_cards` | `updated_at` | `datetime` | | auto-updates |
| `credit_cards` | `api_bin` | `varchar(20)` | | BIN, from the lookup API, on 62% |
| `credit_cards` | `api_marca` | `varchar(60)` | | brand, on 63% |
| `credit_cards` | `api_tipo` | `varchar(60)` | | credit/debit, on 63% |
| `credit_cards` | `api_esquema` | `varchar(60)` | | scheme, on 62% |
| `credit_cards` | `api_pais` | `varchar(60)` | | country, on 62% |
| `credit_cards` | `api_banco` | `varchar(80)` | index | issuer name, on 91% |
| `credit_cards` | `api_actualizado` | `datetime` | index | last BIN refresh, on 13% |

The `api_*` columns are BIN-lookup results cached on the row. `numero` holds the full
number, so `api_bin` is derivable and the card itself is what needs to leave.

## credit_cards_log

Every change to a `credit_cards` row, as before/after JSON. 131,040 rows — 31,567
inserts and 99,473 updates — written today.

| table | column | type | key | note |
|---|---|---|---|---|
| `credit_cards_log` | `id` | `int` | PK, auto_inc | |
| `credit_cards_log` | `credit_card_corr` | `int` | → `credit_cards.corr` | which card |
| `credit_cards_log` | `accion` | `enum` | | `INSERT` / `UPDATE` / `DELETE` |
| `credit_cards_log` | `usuario` | `varchar(100)` | | who changed it |
| `credit_cards_log` | `fecha` | `datetime` | | when |
| `credit_cards_log` | `data_anterior` | `json` | | the row before |
| `credit_cards_log` | `data_nueva` | `json` | | the row after |

This logs edits to the card record, **not charges**. The JSON carries `numero`, so every
historical card number is retained here even after the card row is corrected or deleted.

## Card lookups

| table | column | type | key | note |
|---|---|---|---|---|
| `forma_pago` | `corr` | `int` | PK, auto_inc | |
| `forma_pago` | `descripcion` | `varchar(100)` | | `CRÉDITO` `DÉBITO` `DEPOSITO` |
| `tipo_tarjeta` | `corr` | `int` | PK, auto_inc | |
| `tipo_tarjeta` | `descripcion` | `varchar(100)` | unique | same three values as `forma_pago` |
| `network` | `id` | `int` | PK, auto_inc | |
| `network` | `descripcion` | `varchar(100)` | unique | `VISA` `MASTERCARD` `AMEX` `DINERS` `DISCOVER` `JCB` `UNIONPAY` `DEPOSITO` |
| `type_acquiring` | `id` | `int` | PK, auto_inc | |
| `type_acquiring` | `descripcion` | `varchar(100)` | unique | `PLATINO` `ORO` `CLASICA` |
| `issuing_bank` | `id` | `int` | PK, auto_inc | |
| `issuing_bank` | `descripcion` | `varchar(100)` | unique | 2,374 issuer names |
| `bin_list_tarjetas` | `corr` | `int` | PK, auto_inc | |
| `bin_list_tarjetas` | `bin` | `int` | index | 177,405 BIN ranges |
| `bin_list_tarjetas` | `brand` | `varchar(25)` | | |
| `bin_list_tarjetas` | `type` | `varchar(11)` | | credit / debit |
| `bin_list_tarjetas` | `category` | `varchar(34)` | | |
| `bin_list_tarjetas` | `issuer` | `varchar(96)` | | |
| `bin_list_tarjetas` | `countryname` | `varchar(13)` | | |
| `bin_list_tarjetas` | `isocode3` | `varchar(3)` | | |
| `bin_cache` | `bin` | `int` | PK | live API results, 340 rows |
| `bin_cache` | `scheme` | `varchar(30)` | | |
| `bin_cache` | `type` | `varchar(30)` | | |
| `bin_cache` | `brand` | `varchar(60)` | | |
| `bin_cache` | `bank` | `varchar(80)` | | |
| `bin_cache` | `country` | `varchar(60)` | | |
| `bin_cache` | `updated_at` | `datetime` | | |

`bin_list_tarjetas` is the bulk BIN table; `bin_cache` is the per-BIN cache of the live
API that fills `credit_cards.api_*`.

## Lookup tables

| table | column | type | key | note |
|---|---|---|---|---|
| `tipo_sol` | `id` | `int` | PK | feeds the Medio dropdown → `bita2.TIPOSOL` |
| `tipo_sol` | `name` | `varchar(255)` | | the stored value |
| `tipo_sol` | `title` | `varchar(255)` | | the label shown |
| `tipo_reserva` | `id` | `int` | PK | feeds Tipo Reserva → `bita2.ASUNTO` |
| `tipo_reserva` | `name` | `varchar(255)` | | the stored value |
| `tipo_reserva` | `title` | `varchar(255)` | | the label shown |
| `tipo_unid` | `id` | `int` | PK, auto_inc | room types |
| `tipo_unid` | `unidad` | `varchar(10)` | index | room code |
| `tipo_unid` | `hotel` | `int` | index | hotel |
| `tipo_unid` | `nombre` | `varchar(50)` | | display name |
| `tipo_unid` | `descripcion` | `text` | | description |
| `tipo_unid` | `info` | `text` | | extra info |
| `tipo_unid` | `max_unid` | `int` | | max units |
| `tipo_unid` | `adultos` | `int` | | max adults |
| `tipo_unid` | `ninos` | `int` | | max children |
| `tipo_unid` | `color` | `varchar(50)` | | UI colour |
| `tipo_unid` | `img_portada` | `mediumblob` | | cover image stored in the row |
| `combinaciones` | `id` | `bigint unsigned` | PK, auto_inc | party size to room mapping |
| `combinaciones` | `hotel` | `int` | | hotel |
| `combinaciones` | `adultos` | `tinyint unsigned` | | adults |
| `combinaciones` | `ninos` | `tinyint unsigned` | | children |
| `combinaciones` | `total` | `tinyint unsigned` | | party size |
| `combinaciones` | `prioridad` | `smallint unsigned` | | ordering |
| `combinaciones` | `activo` | `tinyint(1)` | | on/off |
| `combinaciones` | `created_at` | `timestamp` | | |
| `combinaciones` | `updated_at` | `timestamp` | | |
| `destino` | `CORR` | `int` | PK, auto_inc | season and points rates |
| `destino` | `CVELUG` | `int` | index | place code |
| `destino` | `DESTINO` | `varchar(20)` | | season code |
| `destino` | `destino_res` | `varchar(10)` | | season code as used on reservations |
| `destino` | `CVEUNI` | `varchar(10)` | index | room code |
| `destino` | `CVETEM` | `varchar(1)` | | season type |
| `destino` | `CVEEST` | `varchar(1)` | | state |
| `destino` | `NUMPUN` | `decimal(6,1)` | index | points rate |
| `destino` | `IMPCTA` | `decimal(12,2)` | | amount |
| `destino` | `SECPUN` | `int` | | sequence |
| `destino` | `ANOCTA` | `int` | index | year |
| `destino` | `DESUSO` | `varchar(20)` | | usage |
| `destino` | `FINENTRE` | `varchar(6)` | | weekend / weekday |
| `destino` | `LOCALINTER` | `varchar(5)` | | local / international |
| `destino` | `TIPO` | `varchar(10)` | index | type |
| `destino` | `NOM_COMPLETO` | `varchar(50)` | | full name |
| `destino` | `lugaruso` | `varchar(50)` | | place |
| `destino` | `BAJA` | `varchar(1)` | index | inactive flag |

`tipo_sol` holds twelve channels including `mercadeo`, which the form offers but no
`bita2` row has ever stored. `tipo_reserva` holds exactly the seven `ASUNTO` values plus
a blank `Seleccione...` placeholder.

### What the reservation types mean

| value | meaning |
|---|---|
| `PUNTOS` | points drawn from the member's own balance |
| `BONO` | points drawn from the bonus balance — see [bono_otorgado](#bono_otorgado) |
| `CERTIFICADO` | free nights earned with a purchase |
| `INTERCAMBIO` | the member books a whole week and exchanges it for a week abroad through Interval International (<https://intervalinternational.com>), which runs the week exchange |
| `CERTIPUNTOS` `PUNTOSBONO` `MIXTA` | combinations — the header value when the Detalle rows do not all use the same type |

`CERTIFICADO` being free nights is why it has no ledger bucket of its own: 1,426 of the
1,437 certificate quotes still debit `resecut.nor_bono = 'PUNTOS'`, and only 4 land in
`CERTIFICADO`. It records how the stay was authorised, not where the points came from.

## Coded values

Every value below actually occurs in the data.

| table.column | values |
|---|---|
| `bita2.RESULTADO` | `confirmada` `Informacion` `No hay espacios` `Lista de Espera` |
| `bita2.ESTATUS` | `CERRADO` `pendiente` `ANULADO` |
| `bita2.TIPOSOL` | `whatsapp` `telefono` `presencial` `web` `correo` `ventas` `empleado` `inhouse` `otros` `tmk` `webchat` |
| `bita2.ASUNTO` | `PUNTOS` `BONO` `CERTIFICADO` `PUNTOSBONO` `CERTIPUNTOS` `INTERCAMBIO` `MIXTA` |
| `bita2.TIPO_RESERVA` | `PUNTOS` `BONO` `CERTIFICADO` |
| `bita2.HOTEL1` | `1` antigua · `2` pacifico |
| `bita_reserva.ESTATUS` | `UTILIZADA` `CANCELADO` |
| `resecut.TIPDOC` | `VI` `VE` `EX` `EQ` `CT` `EM` `RE` `UP` |
| `resecut.nor_bono` | `PUNTOS` `BONO` `CERTIFICADO` |
| `resecut.CUESTA` | `U` used · `C` cancelled · `R` returned |
| `comen.GRUPO` | `COBROS` `SERVICIO` `POSVENTA` `CREDITOS` |
| `comen.TIPOCOM` | `RECURRENTE` `NORMAL` `CR-NORMAL` `SOLEIL PACIFICO` `CR-NOTIF COBROS` `SOLEIL LA ANTIGUA` `AS-RESERVA` |
| `pasante.TIPCAN` | empty = active · `CV` `19` `AM` `02` `16` `UP` `PS` |
| `solicitudes_allotment.estatus` | `si_hay` `denegada` `pendiente` |
| `tarifa_hotel3.temporada` | `ENTRE SEMANA` `FIN DE SEMANA` `SUPER ALTA` `PROMO` `ENTRE` `FIN` |
| `credit_cards_log.accion` | `INSERT` `UPDATE` `DELETE` |

`bita2.RESULTADO` also holds blanks and two stray values `1` and `2`. `ANULADO` is only
68 rows, all pre-2025.

## Legacy card columns

Card numbers live in the clear in three generations of table, all still present.

| table | column | type | note |
|---|---|---|---|
| `credit_cards` | `numero` | `varchar(25)` | **current** — 39,763 rows, written today |
| `credit_cards_log` | `data_nueva` / `data_anterior` | `json` | every historical value of the above |
| `pasante` | `TARNUMERO` | `varchar(30)` | card on file — 5,897 of 7,662 active members |
| `pasante` | `TARNOMBRE` | `varchar(100)` | cardholder name, and it is **indexed** |
| `pasante` | `tarmes` / `tarano` | `int` | expiry |
| `bita2` | `TARJETA` | `varchar(20)` | 17,305 of 30,174 parse as a 13–19 digit PAN |
| `bita2` | `TARJETAMES` / `TARJETAANO` | `varchar` | expiry |
| `bita2` | `TARJETAEMI` | `varchar(20)` | issuer |
| `bita2` | `COMENTARIO` | `varchar(25)` | nominally a code field; agents type card numbers into it |
| `bita2` | `ASUNTO2` | `varchar(40)` | same — card numbers, NITs and emails as free text |
| `credit_card` | `numero` | `varchar(25)` | 77 rows, superseded by `credit_cards` |
| `credit_card_manif` | `numero` | `varchar(25)` | 8,366 rows, sales-manifest copy |

Keep a processor token plus `last4`, `brand`, `exp_month`, `exp_year` instead, and record
transaction id, auth code, amount, status and timestamp — none of which exists today.
`app/bac.py` already pings `staging.ptranz.com`.

About ten backup copies of `bita2` and `bita_reserva` also live in the schema
(`bita2_bk_26_01_2026`, `bita2_rescue`, `bita2_solo_ingreso`, …) carrying the same card
columns.

## Postgres contracts

**One MySQL table feeds it: `pasante`.** Nothing else is read at load time. `manif`,
`canual` and the stored procedures were used to *prove* the mapping, not to source it.

The key is `contracts.contract_number` = `pasante.JUNTO`, the same key `members` and
`points` already use. `contracts.membership_number` = `pasante.NUMCON`, which is the
reverse of the names — in MySQL `JUNTO` is the membership number and `NUMCON` reads like
"número de contrato", and the Postgres side swaps them.

Loader is `app/temp/fill_contracts.py`, run from the repo root:

```bash
uv run python -m app.temp.fill_contracts
```

Row scope is the 6,360 `contract_number`s already in `members`, which
`app/cron_jobs/update_members_mysql.py` selected with `pasante.ESTATUS = 'ACTIVO'`. 6,358
loaded. All 6,358 rows were diffed column by column against `pasante` afterwards and every
value matches.

### How each column was proved

Three kinds of evidence, strongest first. The `evidence` column in the table below names
which one applies.

**`proc`** — the column appears in `actualizarCuenta`, so its meaning comes from the code
that writes it, not from its name. Two blocks carry almost all of it. The annuity block
computes the monthly payment from three columns, which fixes all three at once:

```sql
SET @interes_dec = (tasanu_var/100)/12;
SET CU = (toca * @interes_dec) / (1 - POW(1 + @interes_dec, -tope));
SET interesInicial = (tope * CU) - toca;
```

so `tasanu` is an annual percent, `TOPE` is the number of installments, `TOCA` is the
financed principal and `toin` is total interest. The single `UPDATE` at the end of the
procedure fixes the rest: `PAIN = interesAcumulado`, `PACA = capitalAcumulado`,
`PECA = capitalPendiente`, `PEIN = interesPendiente`, `PEPE = cuotasPendientes`,
`VECA = capitalVencido`, `VEIN = interesVencido`, `VEPE = cuotasVencidas`,
`paen = varPaen`, `saldofav = varSaldofav`. `varPaen` is itself summed out of `canual`
over the payment transaction types `CHE AC CJ CP CO COS CO1 CO2 EFE TAR CAE EQ DVP`, so
`PAEN` is money actually received against the down payment. The procedure also reads
`(p.TOEN - p.PAEN) AS peen` as the down payment still owed, which is what makes `TOEN` the
total due rather than the amount paid.

**`manif`** — `actualizaPasanteManif` copies the sales manifest onto `pasante`
(`p.valor_original = IF(m.VALOR_COMI = 0, p.precio, m.VALOR_COMI)`,
`p.compra_original = m.FECCON`), and the manifest still agrees on current data:
`valor_original = manif.VALOR_COMI` on 5,791 of 6,062 joined rows and
`compra_original = manif.FECCON` on 5,918. The manifest independently re-confirms two
`proc` columns as well — `CU = manif.IMPMEN` on 5,162 rows and `TOPE = manif.NUMPAG` on
5,187.

**`type`** — the hand-written Postgres DDL copies MySQL precision exactly, so precision
identifies the source column on its own. `contract_price numeric(7,2)` ← `PRECIO
decimal(7,2)`, `capital_overdue numeric(7,2)` ← `VECA decimal(7,2)`, `percent_paid
numeric(8,1)` ← `PORPAG decimal(8,1)`, `contract_term_years numeric(4,1)` ← `POR
decimal(4,1)`, and `monthly_payment varchar(10)` ← `CU varchar(10)` — the money column
that is text on both sides.

### The mapping

| contracts | pasante | type both sides | evidence |
|---|---|---|---|
| `contract_number` | `JUNTO` | `varchar(7)` | key `members` and `points` already use |
| `membership_number` | `NUMCON` | `int` | same as `members.membership_number` |
| `contract_date` | `FECCON` | `date` | name, and `POR` is measured off it |
| `original_purchase_date` | `compra_original` | `date` | `manif` |
| `contract_price` | `PRECIO` | `decimal(7,2)` | `proc` — `varPrecio`, the % paid denominator |
| `original_contract_price` | `valor_original` | `decimal(14,2)` | `manif` |
| `down_payment_agreed` | `paen_original` | `decimal(14,2)` | `type` + the family identity below |
| `down_payment_fees` | `OTROS` | `decimal(12,2)` | `type` + `proc` |
| `down_payment_total_due` | `TOEN` | `decimal(12,2)` | `proc` — `peen = TOEN - PAEN` |
| `down_payment_paid` | `PAEN` | `decimal(10,2)` | `proc` — summed from `canual` |
| `financed_principal` | `TOCA` | `decimal(12,2)` | `proc` — annuity base |
| `financed_principal_paid` | `PACA` | `decimal(12,2)` | `proc` — `capitalAcumulado` |
| `capital_pending` | `PECA` | `decimal(12,2)` | `proc` — `capitalPendiente` |
| `interest_total` | `toin` | `decimal(10,2)` | `proc` — `(tope * CU) - toca` |
| `interest_paid` | `PAIN` | `decimal(12,2)` | `proc` — `interesAcumulado` |
| `interest_outstanding` | `PEIN` | `decimal(12,2)` | `proc` — `interesPendiente` |
| `annual_interest_rate_percent` | `tasanu` | `decimal(6,2)` | `proc` — `(tasanu/100)/12` |
| `percent_paid` | `PORPAG` | `decimal(8,1)` | `type` |
| `previous_contract_number` | `JUNTO_ANT` | `varchar(7)` | name |
| `next_contract_number` | `JUNTO_SIG` | `varchar(7)` | name |
| `installments_total` | `TOPE` | `int` | `proc` + `manif.NUMPAG` |
| `installments_pending` | `PEPE` | `int` | `proc` — `cuotasPendientes` |
| `installments_overdue` | `VEPE` | `int` | `proc` — `cuotasVencidas` |
| `monthly_payment` | `CU` | `varchar(10)` | `proc` + `manif.IMPMEN` |
| `capital_overdue` | `VECA` | `decimal(7,2)` | `proc` — `capitalVencido` |
| `interest_overdue` | `VEIN` | `decimal(12,2)` | `proc` — `interesVencido` |
| `first_payment_date` | `FECPRI` | `date` | `proc` — `fecha_pri` |
| `cancellation_date` | `FECCAN` | `date` | `proc` — `fecha_cancel` |
| `contract_term_years` | `POR` | `decimal(4,1)` | data, see below |
| `credit_balance` | `saldofav` | `decimal(10,2)` | `proc` |
| `expiration_date` | `fecven` | `date` | name, and `POR` is measured to it |

### The down payment is four columns that add up

`down_payment_agreed + down_payment_fees = down_payment_total_due`, and
`paen_original + OTROS = TOEN` holds on 4,311 of 6,361 rows. It is not higher because
`paen_original` is `0.00` on 748 of them. `OTROS` is a flat fee — `485.00` on 3,305 rows,
then `385.00`, `585.00`, `685.00`, and `386.00` on 87 — and `actualizarCuenta` subtracts
it from down payment money before converting to points:

```sql
SET varPunPag = ROUND(((capitalAcumulado + varPaen - varOtros) / varPrecio) * varPuncom, 1);
```

so `OTROS` is the part of the down payment that buys nothing. That is what makes it fees
rather than price. These two are the only columns in the table resting on the identity
plus the type fingerprint rather than on a procedure naming them, so they are the two to
re-check first if a figure looks wrong.

`TOEN = manif.ENGTOT` on 4,255 of 6,062 joined rows, so the manifest's total down payment
already includes the fee.

### POR is the membership term in years, not a percentage

The name reads like *porcentaje* and it is not one. `POR` equals
`ROUND(DATEDIFF(fecven, FECCON)/365.25)` on 6,094 of 6,361 rows, and
`YEAR(fecven) - YEAR(FECCON)` on 5,956. Its values are membership terms — `8.0` on 939
rows, then `5.0`, `10.0`, `25.0`, `9.0`, `14.0`. It is unrelated to the financing length:
the most common pair is `POR = 8.0` with `TOPE = 48`, a 48-month plan on an 8-year
membership. `manif.vigencia` is the same idea on the manifest but agrees on only 1,168
rows, so it is not usable as a check.

### Traps found while loading

`CU` is `varchar(10)` in `pasante` even though every procedure treats it as a decimal, and
`monthly_payment` copies that, so the monthly payment is text on both sides. Longest value
is 8 characters.

Zero dates survive in the date columns and must become `NULL`: `FECPRI` is `0000-00-00` on
303 of the loaded rows, `FECCAN` on 1,118, `fecven` on 5, `compra_original` on 1. `FECCON`
has none. The one contract with a zero `compra_original` could not be loaded at all
because `original_purchase_date` is `NOT NULL`.

`JUNTO_ANT` and `JUNTO_SIG` are `''`, never `NULL`, on 4,637 and 6,351 rows. They arrive as
empty strings, so `previous_contract_number` and `next_contract_number` being `NOT NULL`
costs nothing.

`JUNTO` is not unique in `pasante`. `1209634` has two rows, `CORR` 47616 `ACTIVO` and
47620 `VENCIDO`, identical in every money column. Filtering `ESTATUS = 'ACTIVO'` resolves
it without an arbitrary tiebreak, and matches how `members` was built. One further
`contract_number` in `members` no longer has an `ACTIVO` row in `pasante` at all, so 6,358
loaded out of 6,360.

`PEPE` and `VEPE` are `NULL` on one row, `VECA` on 480.

### Still open

`payment_status` `varchar(30)` is the one column left empty. Two candidates and no way to
choose from the schema alone: `GERENTE varchar(30)` is the exact width match and
`actualizarCuenta` overwrites it with `'PAGADO'` or `''` — 2,564 and 3,797 on the loaded
rows — despite the name meaning sales manager. `SITUA varchar(15)` holds `'0 VENCIDAS'`
on 5,913 rows, `'1 VENCIDA'` on 160, and no procedure references it.

`payment_plan_code` was dropped from `contracts`. No `pasante` column means a payment plan:
`descuento_forma` is a code but has 13 distinct `TOPE` values under its most common value,
`planb_plazo` is a term in months and is `1` on 5,755 rows, `numest` is `43` on 5,839, and
none of the three has a lookup table anywhere in the schema.

`app/models.py` has `Contracts` still carrying `payment_plan_code` and missing
`credit_balance` and `expiration_date`, which the real table has. The loader uses SQL text
rather than the ORM class, so it does not care.
