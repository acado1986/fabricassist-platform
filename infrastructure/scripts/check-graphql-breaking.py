#!/usr/bin/env python3
"""Fail closed on GraphQL breaking changes except exact approved cutovers."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from graphql import build_schema, is_enum_type, is_input_object_type


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def breaking_changes(old_path: Path, new_path: Path) -> set[str]:
    old = build_schema(old_path.read_text())
    new = build_schema(new_path.read_text())
    changes: set[str] = set()
    old_types = {name: value for name, value in old.type_map.items() if not name.startswith("__")}
    new_types = {name: value for name, value in new.type_map.items() if not name.startswith("__")}
    for name, old_type in old_types.items():
        new_type = new_types.get(name)
        if new_type is None:
            changes.add(f"type:{name}")
            continue
        old_fields = getattr(old_type, "fields", {})
        new_fields = getattr(new_type, "fields", {})
        for field_name, old_field in old_fields.items():
            new_field = new_fields.get(field_name)
            if new_field is None:
                changes.add(f"field:{name}.{field_name}")
                continue
            if str(old_field.type) != str(new_field.type):
                changes.add(f"field-type:{name}.{field_name}")
            old_args = getattr(old_field, "args", {})
            new_args = getattr(new_field, "args", {})
            for arg_name, old_arg in old_args.items():
                new_arg = new_args.get(arg_name)
                if new_arg is None:
                    changes.add(f"field-arg:{name}.{field_name}.{arg_name}")
                elif str(old_arg.type) != str(new_arg.type):
                    changes.add(f"field-arg-type:{name}.{field_name}.{arg_name}")
        if is_enum_type(old_type) and is_enum_type(new_type):
            for value in old_type.values:
                if value not in new_type.values:
                    changes.add(f"enum:{name}.{value}")
        if is_input_object_type(old_type) and is_input_object_type(new_type):
            for field_name in old_type.fields:
                if field_name not in new_type.fields:
                    changes.add(f"input-field:{name}.{field_name}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument(
        "--allow-compatible-additions",
        action="store_true",
        help="Allow non-breaking additions after an approved breaking cutover.",
    )
    args = parser.parse_args()

    changes = breaking_changes(args.base, args.current)
    if not changes:
        print("No GraphQL breaking changes detected.")
        return 0

    approval = json.loads(args.approval.read_text())
    approved = set(approval.get("allowed_breaking_changes", []))
    hashes_match = approval.get("base_schema_sha256") == sha256(args.base) and (
        approval.get("new_schema_sha256") == sha256(args.current)
        or args.allow_compatible_additions
    )
    adr_bound = approval.get("adr") in {"ADR-017", "ADR-018"}
    if hashes_match and adr_bound and changes == approved:
        print(
            f"Approved {approval['adr']} GraphQL cutover changes: "
            + ", ".join(sorted(changes))
        )
        return 0

    print("Unapproved GraphQL breaking changes:", file=sys.stderr)
    for change in sorted(changes - approved):
        print(f"  {change}", file=sys.stderr)
    if changes == approved:
        print("The checked-in approval manifest is not bound to these schema hashes.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
