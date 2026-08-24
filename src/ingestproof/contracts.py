"""One declaration per table: the fields, the import-time guards, the job resource.

Generalised out of the flagship's `src/opl/bronze/registry.py`, with no CNPJ vocabulary
travelling with it. A declaration is data; `declare` is what judges one, and it judges
while the declaring module's body is still running -- so a malformed declaration refuses
at import rather than waiting for someone to call into it.

WHAT THE JOB RESOURCE CARRIES, and why it is not a deployable task chain. This library
publishes no job scripts, so an emitter naming `python_file: ../src/<name>_ingest.py`
would be naming a file nothing here ships and nothing here can verify. The resource
carries what the declaration DETERMINES -- the job key, the batch parameter whose default
is a value `require_batch_id` refuses, and the staging/bronze/quarantine triple as tags --
and the consumer wires the tasks.

THE YAML IS EMITTED AND READ BY THIS MODULE, in a deliberately small subset: two-space
indentation, mappings, sequences, and single-quoted scalars. Values are ALWAYS quoted and
keys are quoted unless they are plainly safe, because YAML 1.1 reads `on` as a boolean
and `2026-08-23` as a date -- a table named either would round trip through this module's
own reader and come back as the wrong type from PyYAML.
`tests/acceptance/test_ac01_one_declaration.py` holds PyYAML against the same text for
exactly that reason; this module is one of the two parsers, never both.

THE READER IS THE EMITTER'S INVERSE AND NOTHING WIDER. It refuses every document this
module could not have written -- a bare value, a bare key that is not one `_emit_key`
would leave bare, a half-quoted scalar. That is not strictness for its own sake: a reader
that accepts more than the emitter writes is a reader that can disagree with the referee,
and the disagreement is invisible because both halves are ours. It reports no line
numbers, deliberately: the blank-line filter below makes an index into the filtered list
the wrong number, and a position computed wrongly is worse than none.

[impl->req~ac-01~1]
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, fields

# The job parameter's default, and its whole job is to fail. A job parameter has to have
# SOME default and no batch id is a valid one, so a default that happened to be a real
# batch id would let every un-parameterised run promote under a batch nobody chose.
# `require_batch_id` is what refuses it.
SENTINEL_BATCH_ID = "REQUIRED-PASS-A-BATCH-ID"

# The columns this library stamps itself. Not the source columns -- those come from the
# declared source dialect, which is layer 2, and a declaration cannot know them.
BATCH_ID_COLUMN = "_batch_id"
CONTRACT_ID_COLUMN = "_contract_id"
REJECTED_BY_COLUMN = "_rejected_by"

AUDIT_SCHEMA = (
    (BATCH_ID_COLUMN, "string"),
    (CONTRACT_ID_COLUMN, "string"),
    (REJECTED_BY_COLUMN, "string"),
)

JOB_NAME_PREFIX = "ingestproof-"
TAG_PREFIX = "ingestproof_"

# A key is emitted bare only if it matches this AND is not one of the YAML 1.1 words a
# parser MAY resolve to a bool or a null. Everything else is quoted. Measured against
# PyYAML 6: 21 of the 25 below come back as a non-string key and `y`, `Y`, `n`, `N` do
# not, because PyYAML's bool resolver omits the single-letter forms. They stay in the set
# because PyYAML is the acceptance test's referee and not the parser that reads a bundle.
PLAIN_KEY = re.compile(r"\A[A-Za-z_][A-Za-z0-9_-]*\Z")
RESERVED_PLAIN_WORDS = frozenset(
    {
        "y", "yes", "n", "no", "true", "false", "on", "off",
        "Y", "Yes", "N", "No", "True", "False", "On", "Off",
        "YES", "NO", "TRUE", "FALSE", "ON", "OFF",
        "null", "Null", "NULL",
    }
)

# U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR. YAML 1.1 lists both as line
# breaks. PyYAML 6 does NOT -- measured, both round trip through it unchanged -- so this
# refusal is not for the referee in the acceptance test but for the parser that reads a
# bundle, exactly as `y` and `n` stay in RESERVED_PLAIN_WORDS above.
YAML_LINE_SEPARATORS = ("\u2028", "\u2029")

# The two non-characters, and they are here because CATEGORY IS THE WRONG QUESTION for
# them. Measured against PyYAML 6's own Reader.NON_PRINTABLE, the code points it refuses
# outright are U+0000..0008, U+000B..000C, U+000E..001F, U+007F..0084, U+0086..009F,
# U+FFFE..FFFF and the surrogates. Category `Cc` covers the four middle ranges; category
# `Cn` would cover U+FFFE and U+FFFF but ALSO U+FDD0, which PyYAML reads back unchanged --
# so `Cn` refuses more than measurement asks for. These two are named instead.
NONCHARACTERS = ("\ufffe", "\uffff")

# YAML bounds a simple key at 1024 characters. Measured: a table name of 1024 round trips
# through PyYAML and 1025 raises ScannerError, while a VALUE of 5000 is fine -- the bound
# is the key's, so it is checked where the key token is built and nowhere else.
MAX_SIMPLE_KEY = 1024

INDENT = 2

# Two columns, and it is the same two as INDENT rather than coincidentally equal: a
# sequence item's children are emitted at `indent + INDENT` and have to line up under the
# text that follows the dash. Measured -- emitting at INDENT=3 or INDENT=4 leaves this
# module's own reader round tripping while PyYAML raises ParserError. INDENT is therefore
# not configuration, and `test_the_marker_and_the_indent_are_one_number` says so.
SEQUENCE_MARKER = "- "

type Yaml = str | list[Yaml] | dict[str, Yaml]


class ContractError(Exception):
    """A declaration this library refuses. Raised while the declaring module body runs."""


@dataclass(frozen=True)
class TableContract:
    """One table's declaration. Frozen: a contract a caller can mutate is not a contract."""

    name: str
    contract_id: str
    staging: str
    bronze: str
    quarantine: str
    landing_mode: str | None
    prefix: str
    constraints: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TablePlan:
    """What one declaration comes out with. The criterion's own list, in its own order."""

    schema: tuple[tuple[str, str], ...]
    rules: tuple[tuple[str, str], ...]
    quarantine: dict[str, str]
    promotion: dict[str, str]
    job_yaml: str


# PROCESS-WIDE, and that is a real cost rather than an oversight. `register` takes an id
# and nothing else -- the frozen acceptance test calls `register("no-such-contract-id")`
# from a module that imported only the three public names -- so the mapping has to live
# somewhere the lookup can reach without being handed it. The cost is that declarations
# leak between callers in one process, which for the test ring is handled by the autouse
# fixture in `tests/unit/conftest.py`.
_REGISTRY: dict[str, TableContract] = {}


def require_batch_id(batch_id: str) -> str:
    """Refuse the sentinel the job resource carries as its default.

    Without this the sentinel is decoration: a default that says REQUIRED and is then
    accepted is a default that runs.
    """
    if batch_id == SENTINEL_BATCH_ID:
        raise ContractError(
            f"batch id is still the job parameter's default {SENTINEL_BATCH_ID!r}: "
            "launch the run with an explicit batch id"
        )
    if not batch_id:
        raise ContractError("batch id is empty")
    return batch_id


def register(contract_id: str) -> TableContract:
    """Look a declared contract up by id, or refuse.

    The registry maps one id to one contract, and `declare` refuses to rebind an id to a
    different declaration -- not a fourth guard, but the invariant that makes this a
    lookup: an id that could answer either of two contracts answers nothing.
    """
    try:
        return _REGISTRY[contract_id]
    except KeyError:
        raise ContractError(f"unknown contract {contract_id!r}") from None


def declare(contract: TableContract) -> TablePlan:
    """Judge one declaration, register it, and return what it comes out with."""
    if contract.prefix != contract.name + "_":
        raise ContractError(
            f"prefix {contract.prefix!r} matches no file group for table "
            f"{contract.name!r}: expected {contract.name + '_'!r}"
        )

    landing_mode = contract.landing_mode
    if not landing_mode:
        raise ContractError(f"table {contract.name!r} declares no landing mode, so it has no job")

    already = _REGISTRY.get(contract.contract_id)
    if already is not None and already != contract:
        differing = ", ".join(
            field.name
            for field in fields(contract)
            if getattr(already, field.name) != getattr(contract, field.name)
        )
        raise ContractError(
            f"contract {contract.contract_id!r} is already bound to a declaration that "
            f"differs in {differing}"
        )

    # THE PLAN IS BUILT BEFORE THE REGISTRY IS TOUCHED, and the order is the whole point.
    # `job_yaml` refuses a declaration carrying a character with no one-line YAML scalar,
    # and it refuses it HERE. Registering first left `declare` raising while `register`
    # went on answering with the contract it had just rejected -- a refusal that refuses
    # nothing, which is fail-open by another name.
    plan = TablePlan(
        schema=AUDIT_SCHEMA,
        rules=contract.constraints,
        quarantine={
            "table": contract.quarantine,
            "keyed_on": BATCH_ID_COLUMN,
            "reason_column": REJECTED_BY_COLUMN,
        },
        promotion={
            "source": contract.staging,
            "target": contract.bronze,
            "keyed_on": BATCH_ID_COLUMN,
            "mode": landing_mode,
            "on_rule_error": "quarantine",
        },
        job_yaml=job_yaml(contract),
    )
    _REGISTRY[contract.contract_id] = contract
    return plan


def job_resource(contract: TableContract) -> dict[str, Yaml]:
    """One declaration in, one bundle resource out. Every value is a string, on purpose.

    A sequence comes back from PyYAML as a list and never as the tuple the declaration
    carried, so nothing here may be a tuple; and nothing here is None.
    """
    return {
        "resources": {
            "jobs": {
                contract.name: {
                    "name": JOB_NAME_PREFIX + contract.name,
                    "parameters": [
                        {"name": "batch_id", "default": SENTINEL_BATCH_ID},
                        {"name": "contract_id", "default": contract.contract_id},
                    ],
                    "tags": {
                        TAG_PREFIX + "staging": contract.staging,
                        TAG_PREFIX + "bronze": contract.bronze,
                        TAG_PREFIX + "quarantine": contract.quarantine,
                    },
                }
            }
        }
    }


def job_yaml(contract: TableContract) -> str:
    """The bundle resource as text, in the subset `load_job_yaml` reads back."""
    return _emit(job_resource(contract), 0) + "\n"


def load_job_yaml(text: str) -> Yaml:
    """This module's own reader for the subset this module emits.

    It is one of the two parsers the acceptance criterion needs, never both: a round trip
    through a single parser is green for an emitter that emits no YAML at all.
    """
    # A BOM and a CR are both things a file acquires on the way to disk rather than from
    # this emitter. Measured: written with `encoding="utf-8-sig"` and read back plainly,
    # the un-normalised reader answered a top-level key of \ufeff-resources with no
    # error at all -- a structurally valid mapping that is simply the wrong one.
    normalised = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in normalised.split("\n") if line.strip()]
    if not lines:
        raise ContractError("empty document")
    value, consumed = _read(lines, 0, _indent_of(lines[0]))
    if consumed != len(lines):
        raise ContractError(f"trailing content below the document: {lines[consumed]!r}")
    return value


def _quote(value: str) -> str:
    # A single-quoted YAML scalar is one line. A newline inside one is legal YAML and
    # FOLDS -- it comes back as a space -- so emitting a declaration that carries one
    # would round trip through a different string, silently. Refuse instead.
    #
    # CATEGORY `Cc` AND `Cs`, PLUS TWO NAMED CODE POINTS. `ord(c) < 0x20 or ord(c) ==
    # 0x7F` stood here and let the C1 block through: measured, U+0085 does not round trip
    # through PyYAML 6 and U+009F makes its reader raise. `Cc` is both control blocks;
    # `Cs` is the surrogates, which PyYAML's reader also refuses; and NONCHARACTERS is the
    # last pair, which no category names without naming more than measurement asks for.
    for character in value:
        if (
            unicodedata.category(character) in ("Cc", "Cs")
            or character in YAML_LINE_SEPARATORS
            or character in NONCHARACTERS
        ):
            raise ContractError(
                f"control character or line separator in {value!r}: "
                "it has no one-line YAML scalar"
            )
    return "'" + value.replace("'", "''") + "'"


def _unquote(token: str) -> str:
    if len(token) >= 2 and token.startswith("'") and token.endswith("'"):
        return token[1:-1].replace("''", "'")
    return token


def _scalar(token: str) -> str:
    """A VALUE, which this module always emits quoted -- so anything else is not ours.

    `_unquote` alone read `'unterminated` as the string it looks like, because it only
    strips when both ends are quotes. That is a document this emitter cannot produce and
    PyYAML refuses, being read as data.
    """
    if not token.startswith("'") or _closing_quote(token) != len(token) - 1:
        raise ContractError(f"value is not one complete single-quoted scalar: {token!r}")
    return _unquote(token)


def _emit_key(key: str) -> str:
    token = key if PLAIN_KEY.match(key) and key not in RESERVED_PLAIN_WORDS else _quote(key)
    if len(token) > MAX_SIMPLE_KEY:
        raise ContractError(
            f"key is {len(token)} characters and YAML bounds a simple key at "
            f"{MAX_SIMPLE_KEY}: {key[:40]!r}..."
        )
    return token


def _read_key(token: str) -> str:
    """The inverse of `_emit_key`, and refusing anything it would not have written.

    Without this the reader answered `{'on': 'v'}` where PyYAML answers `{True: 'v'}` --
    the emitter quotes that key precisely so the two agree, and a reader accepting the
    bare form re-opened the hole from the other side.
    """
    if token.startswith("'"):
        if _closing_quote(token) != len(token) - 1:
            raise ContractError(f"key is not one complete single-quoted scalar: {token!r}")
        return _unquote(token)
    if not PLAIN_KEY.match(token) or token in RESERVED_PLAIN_WORDS:
        raise ContractError(f"key is not one this module would emit bare: {token!r}")
    return token


def _emit(node: list[Yaml] | dict[str, Yaml], indent: int) -> str:
    if not node:
        raise ContractError("an empty mapping or sequence has no round trip")
    if isinstance(node, list):
        return _emit_sequence(node, indent)
    return _emit_mapping(node, indent)


def _emit_mapping(node: dict[str, Yaml], indent: int) -> str:
    pad = " " * indent
    lines = []
    for key, value in node.items():
        if isinstance(value, str):
            lines.append(f"{pad}{_emit_key(key)}: {_quote(value)}")
        else:
            lines.append(f"{pad}{_emit_key(key)}:")
            lines.append(_emit(value, indent + INDENT))
    return "\n".join(lines)


def _emit_sequence(node: list[Yaml], indent: int) -> str:
    pad = " " * indent
    lines = []
    for item in node:
        if isinstance(item, str):
            lines.append(f"{pad}{SEQUENCE_MARKER}{_quote(item)}")
            continue
        block = _emit(item, indent + INDENT)
        first, _, rest = block.partition("\n")
        lines.append(pad + SEQUENCE_MARKER + first[indent + INDENT :])
        if rest:
            lines.append(rest)
    return "\n".join(lines)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _closing_quote(content: str) -> int:
    index = 1
    while index < len(content):
        if content[index] == "'":
            if content[index + 1 : index + 2] == "'":
                index += 2
                continue
            return index
        index += 1
    raise ContractError(f"unterminated quoted scalar: {content!r}")


def _split_entry(content: str) -> tuple[str, str]:
    """Key and value of one mapping line, splitting on the colon that ENDS the key.

    A quoted key may contain a colon, so `partition` alone would cut one in half. A
    quoted value may too, and that one is safe: the first colon still ends the key.
    """
    if content.startswith("'"):
        end = _closing_quote(content)
        rest = content[end + 1 :]
        if not rest.startswith(":"):
            raise ContractError(f"quoted key is not followed by a colon: {content!r}")
        return content[: end + 1], rest[1:].strip()
    key, separator, value = content.partition(":")
    if not separator:
        raise ContractError(f"not a mapping entry: {content!r}")
    return key.strip(), value.strip()


def _read(lines: list[str], start: int, indent: int) -> tuple[Yaml, int]:
    if lines[start].lstrip(" ").startswith(SEQUENCE_MARKER):
        return _read_sequence(lines, start, indent)
    return _read_mapping(lines, start, indent)


def _read_mapping(lines: list[str], start: int, indent: int) -> tuple[Yaml, int]:
    out: dict[str, Yaml] = {}
    index = start
    while (
        index < len(lines)
        and _indent_of(lines[index]) == indent
        and not lines[index].lstrip(" ").startswith(SEQUENCE_MARKER)
    ):
        key_token, value_token = _split_entry(lines[index].strip())
        key = _read_key(key_token)
        if value_token:
            out[key] = _scalar(value_token)
            index += 1
            continue
        nested = index + 1
        if nested >= len(lines) or _indent_of(lines[nested]) <= indent:
            raise ContractError(f"key {key!r} opens a block and nothing is indented under it")
        out[key], index = _read(lines, nested, _indent_of(lines[nested]))
    return out, index


def _read_sequence(lines: list[str], start: int, indent: int) -> tuple[Yaml, int]:
    out: list[Yaml] = []
    index = start
    inner = indent + INDENT
    while (
        index < len(lines)
        and _indent_of(lines[index]) == indent
        and lines[index].lstrip(" ").startswith(SEQUENCE_MARKER)
    ):
        rest = lines[index].lstrip(" ")[len(SEQUENCE_MARKER) :]
        if rest.startswith("'") and _closing_quote(rest) == len(rest) - 1:
            out.append(_unquote(rest))
            index += 1
            continue
        value, consumed = _read([" " * inner + rest, *lines[index + 1 :]], 0, inner)
        # `_read` answers 0 when the line it was handed does not sit at the indent it was
        # called with, which happens here for any entry whose dash is followed by more
        # than one space -- `-  'a'`. Without this the index never advances, the same line
        # is re-read forever and `out` grows without bound: measured at 1.2 million calls
        # in three seconds on a two-line document. A loop that can fail to advance is the
        # defect; refusing the input is only the instance.
        if consumed == 0:
            raise ContractError(f"sequence entry is not indented by {INDENT}: {lines[index]!r}")
        out.append(value)
        index += consumed
    return out, index
