"""One declaration per table: the fields, the import-time guards, the job resource.

Generalised out of the flagship's `src/opl/bronze/registry.py`, with no CNPJ vocabulary
travelling with it. A declaration is data; `declare` is the only thing that judges one,
and it judges while the declaring module's body is still running -- so a malformed
declaration refuses at import rather than waiting for someone to call into it.

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
own reader and come back as the wrong type from any other parser.
`tests/acceptance/test_ac01_one_declaration.py` holds PyYAML against the same text for
exactly that reason; this module is one of the two parsers, never both.

[impl->req~ac-01~1]
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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

INDENT = 2

Yaml = str | list["Yaml"] | dict[str, "Yaml"]


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
    different table -- not a fourth guard, but the invariant that makes this a lookup: an
    id that could answer either of two contracts answers nothing.
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
        raise ContractError(
            f"contract {contract.contract_id!r} is already bound to table {already.name!r}"
        )
    _REGISTRY[contract.contract_id] = contract

    return TablePlan(
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


def job_resource(contract: TableContract) -> dict[str, Yaml]:
    """One declaration in, one bundle resource out. Every value is a string, on purpose.

    A sequence comes back from any YAML parser as a list and never as the tuple the
    declaration carried, so nothing here may be a tuple; and nothing may be None, which
    is the other thing a YAML round trip cannot return unchanged as itself.
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
    return _emit(job_resource(contract), 0) + "\n"


def load_job_yaml(text: str) -> Yaml:
    """This module's own reader for the subset this module emits.

    It is one of the two parsers the acceptance criterion needs, never both: a round trip
    through a single parser is green for an emitter that emits no YAML at all.
    """
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        raise ContractError("empty document")
    value, consumed = _read(lines, 0, _indent_of(lines[0]))
    if consumed != len(lines):
        raise ContractError(f"trailing content at line {consumed + 1}: {lines[consumed]!r}")
    return value


def _quote(value: str) -> str:
    # A single-quoted YAML scalar is one line. A newline inside one is legal YAML and
    # FOLDS -- it comes back as a space -- so emitting a declaration that carries one
    # would round trip through a different string, silently. Refuse instead.
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ContractError(f"control character in {value!r}: it has no one-line YAML scalar")
    return "'" + value.replace("'", "''") + "'"


def _unquote(token: str) -> str:
    if len(token) >= 2 and token.startswith("'") and token.endswith("'"):
        return token[1:-1].replace("''", "'")
    return token


def _emit_key(key: str) -> str:
    if PLAIN_KEY.match(key) and key not in RESERVED_PLAIN_WORDS:
        return key
    return _quote(key)


def _emit(node: Yaml, indent: int) -> str:
    if isinstance(node, str):
        raise ContractError("a scalar is emitted by its parent, never as a document")
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
            lines.append(f"{pad}- {_quote(item)}")
            continue
        block = _emit(item, indent + INDENT)
        first, _, rest = block.partition("\n")
        lines.append(pad + "- " + first[indent + INDENT :])
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
    if lines[start].lstrip(" ").startswith("- "):
        return _read_sequence(lines, start, indent)
    return _read_mapping(lines, start, indent)


def _read_mapping(lines: list[str], start: int, indent: int) -> tuple[Yaml, int]:
    out: dict[str, Yaml] = {}
    index = start
    while (
        index < len(lines)
        and _indent_of(lines[index]) == indent
        and not lines[index].lstrip(" ").startswith("- ")
    ):
        key_token, value_token = _split_entry(lines[index].strip())
        key = _unquote(key_token)
        if value_token:
            out[key] = _unquote(value_token)
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
        and lines[index].lstrip(" ").startswith("- ")
    ):
        rest = lines[index].lstrip(" ")[2:]
        if rest.startswith("'") and _closing_quote(rest) == len(rest) - 1:
            out.append(_unquote(rest))
            index += 1
            continue
        value, consumed = _read([" " * inner + rest, *lines[index + 1 :]], 0, inner)
        out.append(value)
        index += consumed
    return out, index
