"""Command-line parser registration for Houdini digital assets."""

from __future__ import annotations

import argparse
from typing import Any

from .hda_inspect import handle_definitions, handle_inspect, handle_libraries
from .hda_lifecycle import (
    handle_create,
    handle_install,
    handle_instantiate,
    handle_match,
    handle_package,
    handle_save,
    handle_uninstall,
    handle_unlock,
    handle_update,
)
from .hda_parms import (
    handle_parms_apply,
    handle_parms_defaults,
    handle_parms_inspect,
    handle_parms_promote,
)
from .hda_sections import (
    SCRIPT_SECTIONS,
    handle_script_delete,
    handle_script_get,
    handle_script_set,
    handle_section_delete,
    handle_section_get,
    handle_section_list,
    handle_section_set,
    handle_tool_inspect,
    handle_tool_remove,
    handle_tool_set,
)
from .hda_validate import handle_validate


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "hda", help="Create, inspect, update, package, and validate digital assets."
    )
    subs = parser.add_subparsers(dest="hda_command", required=True)

    inspect = subs.add_parser("inspect", help="Inspect an HDA instance and definition.")
    inspect.add_argument("asset_node")
    inspect.add_argument("--parms", action="store_true")
    inspect.add_argument("--sections", action="store_true")
    inspect.add_argument("--tools", action="store_true")
    inspect.set_defaults(handler=handle_inspect)

    definitions = subs.add_parser(
        "definitions", help="List installed or file-contained definitions."
    )
    definitions.add_argument("--library")
    definitions.add_argument("--category")
    definitions.add_argument("--namespace")
    definitions.add_argument("--name")
    definitions.set_defaults(handler=handle_definitions)

    libraries = subs.add_parser("libraries", help="List loaded HDA libraries and definitions.")
    libraries.set_defaults(handler=handle_libraries)

    create = subs.add_parser("create", help="Convert a plain subnet into an HDA.")
    create.add_argument("subnet_path")
    _add_creation_args(create)
    create.set_defaults(handler=handle_create)

    package = subs.add_parser("package", help="Package and validate an existing plain subnet.")
    package.add_argument("subnet_path")
    _add_creation_args(package)
    package.add_argument("--tab-submenu")
    package.add_argument("--expanded-preview", action="store_true")
    package.add_argument("--no-validate", action="store_true")
    package.set_defaults(handler=handle_package)

    save = subs.add_parser("save", help="Save an HDA definition.")
    save.add_argument("asset_node")
    save.add_argument("--library")
    save.set_defaults(handler=handle_save)

    instantiate = subs.add_parser("instantiate", help="Create an HDA instance.")
    instantiate.add_argument("type_name")
    instantiate.add_argument("--parent", required=True)
    instantiate.add_argument("--name")
    instantiate.add_argument("--input")
    instantiate.add_argument("--expanded", action="store_true")
    instantiate.set_defaults(handler=handle_instantiate)

    unlock = subs.add_parser("unlock", help="Allow editing of HDA contents.")
    unlock.add_argument("asset_node")
    unlock.add_argument("--propagate", action="store_true")
    unlock.set_defaults(handler=handle_unlock)

    match = subs.add_parser("match", help="Match an instance to its current definition.")
    match.add_argument("asset_node")
    match.add_argument("--force", action="store_true")
    match.set_defaults(handler=handle_match)

    install = subs.add_parser("install", help="Install an HDA library.")
    install.add_argument("library")
    install.add_argument("--force", action="store_true")
    install.set_defaults(handler=handle_install)

    uninstall = subs.add_parser("uninstall", help="Uninstall an HDA library.")
    uninstall.add_argument("library")
    uninstall.add_argument("--force", action="store_true")
    uninstall.set_defaults(handler=handle_uninstall)

    update = subs.add_parser(
        "update", help="Update selected definition surfaces from an instance."
    )
    update.add_argument("asset_node")
    update.add_argument("--contents", action="store_true")
    update.add_argument("--interface", action="store_true")
    update.add_argument("--sections", action="store_true")
    update.add_argument("--tools", action="store_true")
    update.add_argument("--all", action="store_true")
    update.add_argument("--no-save", action="store_true")
    update.add_argument("--no-match", action="store_true")
    update.add_argument("--validate", action="store_true")
    update.set_defaults(handler=handle_update)

    validate = subs.add_parser("validate", help="Validate an HDA definition and instance.")
    validate.add_argument("asset_node")
    validate.add_argument("--fresh-instance", action="store_true")
    validate.add_argument("--cook", action="store_true")
    validate.add_argument("--frames")
    validate.add_argument("--strict", action="store_true")
    validate.set_defaults(handler=handle_validate)

    _register_section(subs)
    _register_script(subs)
    _register_tool(subs)
    _register_parms(subs)


def _add_creation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--type-name", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--min-inputs", type=int, default=0)
    parser.add_argument("--max-inputs", type=int, default=0)
    parser.add_argument("--icon")
    parser.add_argument("--comment")
    parser.add_argument("--definition-version")
    parser.add_argument("--create-dirs", action="store_true")
    parser.add_argument("--create-backup", action="store_true")
    parser.add_argument("--on-existing", choices=("error", "update", "replace"), default="error")


def _register_section(subs: Any) -> None:
    parser = subs.add_parser("section", help="Manage embedded definition sections.")
    nested = parser.add_subparsers(dest="hda_section_command", required=True)
    listing = nested.add_parser("list")
    listing.add_argument("asset_node")
    listing.set_defaults(handler=handle_section_list)
    get = nested.add_parser("get")
    get.add_argument("asset_node")
    get.add_argument("name")
    get.add_argument("--output")
    get.set_defaults(handler=handle_section_get)
    set_cmd = nested.add_parser("set")
    set_cmd.add_argument("asset_node")
    set_cmd.add_argument("name")
    set_cmd.add_argument("--input", required=True)
    set_cmd.add_argument("--no-save", action="store_true")
    set_cmd.set_defaults(handler=handle_section_set)
    delete = nested.add_parser("delete")
    delete.add_argument("asset_node")
    delete.add_argument("name")
    delete.add_argument("--force", action="store_true")
    delete.add_argument("--no-save", action="store_true")
    delete.set_defaults(handler=handle_section_delete)


def _register_script(subs: Any) -> None:
    parser = subs.add_parser("script", help="Manage common HDA script sections.")
    nested = parser.add_subparsers(dest="hda_script_command", required=True)
    handlers = (
        ("get", handle_script_get),
        ("set", handle_script_set),
        ("delete", handle_script_delete),
    )
    for command, handler in handlers:
        child = nested.add_parser(command)
        child.add_argument("asset_node")
        child.add_argument("name", choices=sorted(SCRIPT_SECTIONS))
        if command == "get":
            child.add_argument("--output")
        elif command == "set":
            child.add_argument("--input", required=True)
            child.add_argument("--no-save", action="store_true")
        else:
            child.add_argument("--force", action="store_true")
            child.add_argument("--no-save", action="store_true")
        child.set_defaults(handler=handler)


def _register_tool(subs: Any) -> None:
    parser = subs.add_parser("tool", help="Manage generated Tab-menu tool metadata.")
    nested = parser.add_subparsers(dest="hda_tool_command", required=True)
    inspect = nested.add_parser("inspect")
    inspect.add_argument("asset_node")
    inspect.set_defaults(handler=handle_tool_inspect)
    set_cmd = nested.add_parser("set")
    set_cmd.add_argument("asset_node")
    set_cmd.add_argument("--submenu", required=True)
    set_cmd.add_argument("--context", default="COP")
    set_cmd.add_argument("--icon")
    set_cmd.set_defaults(handler=handle_tool_set)
    remove = nested.add_parser("remove")
    remove.add_argument("asset_node")
    remove.add_argument("--force", action="store_true")
    remove.set_defaults(handler=handle_tool_remove)


def _register_parms(subs: Any) -> None:
    parser = subs.add_parser("parms", help="Inspect and manage HDA interfaces.")
    nested = parser.add_subparsers(dest="hda_parms_command", required=True)
    inspect = nested.add_parser("inspect")
    inspect.add_argument("asset_node")
    inspect.set_defaults(handler=handle_parms_inspect)
    apply_cmd = nested.add_parser("apply")
    apply_cmd.add_argument("asset_node")
    apply_cmd.add_argument("--input", required=True)
    apply_cmd.add_argument("--replace-all", action="store_true")
    apply_cmd.set_defaults(handler=handle_parms_apply)
    promote = nested.add_parser("promote")
    promote.add_argument("asset_node")
    promote.add_argument("internal_parm")
    promote.add_argument("--name", required=True)
    promote.add_argument("--label")
    promote.add_argument("--folder")
    promote.add_argument("--default", choices=("current", "source-default"), default="current")
    promote.set_defaults(handler=handle_parms_promote)
    defaults = nested.add_parser("defaults")
    defaults.add_argument("asset_node")
    defaults.add_argument("--from-current", action="store_true")
    defaults.set_defaults(handler=handle_parms_defaults)
