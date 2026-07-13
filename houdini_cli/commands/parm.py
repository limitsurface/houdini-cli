"""Parameter commands."""

from __future__ import annotations

import argparse

from .node_parms import handle_node_parms_find, handle_node_parms_list
from .parm_expressions import (
    handle_expression_clear,
    handle_expression_get,
    handle_expression_set,
    handle_reference,
)
from .parm_refs import handle_find, handle_refs
from .parm_templates import handle_default_set, handle_template_get, handle_template_set
from .parm_values import (
    handle_full,
    handle_full_set,
    handle_get,
    handle_menu,
    handle_set,
    handle_text_set,
    handle_tuple_set,
)


def register_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parm_parser = subparsers.add_parser("parm", help="Inspect and modify parameters.")
    parm_subparsers = parm_parser.add_subparsers(dest="parm_command", required=True)

    get_parser = parm_subparsers.add_parser("get", help="Get parameter value data.")
    get_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    get_parser.set_defaults(handler=handle_get)

    full_parser = parm_subparsers.add_parser("full", help="Get full structured parameter data.")
    full_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    full_parser.set_defaults(handler=handle_full)

    menu_parser = parm_subparsers.add_parser("menu", help="Get menu tokens and labels for a parameter.")
    menu_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    menu_parser.set_defaults(handler=handle_menu)

    set_parser = parm_subparsers.add_parser("set", help="Set a scalar or single string parameter value.")
    set_parser.add_argument("parm_path", help="Full Houdini parameter path.")
    set_parser.add_argument("value", help="Parameter value.")
    set_parser.set_defaults(handler=handle_set)

    tuple_set_parser = parm_subparsers.add_parser("tuple-set", help="Set tuple parameter values.")
    tuple_set_parser.add_argument("parm_path", help="Tuple parameter path.")
    tuple_set_parser.add_argument("values", nargs="+", help="Tuple component values in order.")
    tuple_set_parser.set_defaults(handler=handle_tuple_set)

    text_set_parser = parm_subparsers.add_parser("text-set", help="Set a text parameter from stdin or a file.")
    text_set_parser.add_argument("parm_path", help="Parameter path.")
    text_set_parser.add_argument("--input", required=True, help="File path or '-' to read from stdin.")
    text_set_parser.set_defaults(handler=handle_text_set)

    full_set_parser = parm_subparsers.add_parser("full-set", help="Apply full structured parameter data.")
    full_set_parser.add_argument("parm_path", help="Parameter path.")
    full_set_parser.add_argument("--input", required=True, help="File path or '-' to read JSON from stdin.")
    full_set_parser.set_defaults(handler=handle_full_set)

    expression_parser = parm_subparsers.add_parser("expression", help="Inspect or modify parameter expressions.")
    expression_subparsers = expression_parser.add_subparsers(dest="parm_expression_command", required=True)

    expression_get_parser = expression_subparsers.add_parser("get", help="Read a parameter expression.")
    expression_get_parser.add_argument("parm_path")
    expression_get_parser.set_defaults(handler=handle_expression_get)

    expression_set_parser = expression_subparsers.add_parser("set", help="Set a parameter expression.")
    expression_set_parser.add_argument("parm_path")
    expression_set_parser.add_argument("--language", choices=("hscript", "python"), default="hscript")
    expression_set_parser.add_argument("--text", help="Expression text.")
    expression_set_parser.add_argument("--input", help="File path or '-' to read expression text.")
    expression_set_parser.set_defaults(handler=handle_expression_set)

    expression_clear_parser = expression_subparsers.add_parser("clear", help="Clear parameter keyframes/expressions.")
    expression_clear_parser.add_argument("parm_path")
    expression_clear_parser.add_argument("--keep-value", action="store_true")
    expression_clear_parser.set_defaults(handler=handle_expression_clear)

    reference_parser = parm_subparsers.add_parser("reference", help="Reference one parameter from another.")
    reference_parser.add_argument("target_parm", help="Parameter that will receive the reference.")
    reference_parser.add_argument("source_parm", help="Parameter to reference.")
    reference_mode = reference_parser.add_mutually_exclusive_group()
    reference_mode.add_argument("--relative", action="store_true", help="Use a relative HScript reference.")
    reference_mode.add_argument("--absolute", action="store_true", help="Use an absolute HScript reference.")
    reference_parser.set_defaults(handler=handle_reference)

    find_parser = parm_subparsers.add_parser("find", help="Search parameter names, values, expressions, and references on one node.")
    find_parser.add_argument("node_path", help="Node path to inspect.")
    find_parser.add_argument("--query", required=True, help="Case-insensitive text to search for.")
    find_parser.add_argument("--raw", action="store_true", help="Include raw parameter values in matching rows.")
    find_parser.add_argument("--expressions", action="store_true", help="Include expression text in matching rows.")
    find_parser.add_argument("--resolved-targets", action="store_true", help="Include resolved referenced parameter paths.")
    find_parser.add_argument("--max-matches", type=int, default=100, help="Maximum matching parameters to return.")
    find_parser.set_defaults(handler=handle_find)

    refs_parser = parm_subparsers.add_parser("refs", help="List resolved parameter references on one node.")
    refs_parser.add_argument("node_path", help="Node path to inspect.")
    refs_parser.add_argument("--external-to", help="Mark references outside this node/network root.")
    refs_parser.add_argument("--recursive", action="store_true", help="Include child nodes below node_path.")
    refs_parser.add_argument("--max-refs", type=int, default=100, help="Maximum references to return.")
    refs_parser.set_defaults(handler=handle_refs)

    template_parser = parm_subparsers.add_parser("template", help="Inspect or modify parameter templates.")
    template_subparsers = template_parser.add_subparsers(dest="parm_template_command", required=True)

    template_get_parser = template_subparsers.add_parser("get", help="Read a parameter template summary.")
    template_get_parser.add_argument("parm_path")
    template_get_parser.add_argument("--target", choices=("instance", "definition"), default="instance")
    template_get_parser.set_defaults(handler=handle_template_get)

    template_set_parser = template_subparsers.add_parser("set", help="Apply a partial parameter template patch.")
    template_set_parser.add_argument("parm_path")
    template_set_parser.add_argument("--target", choices=("instance", "definition"), default="instance")
    template_set_parser.add_argument("--input", required=True, help="JSON file path or '-' for stdin.")
    template_set_parser.set_defaults(handler=handle_template_set)

    default_parser = parm_subparsers.add_parser("default", help="Set a parameter-template default.")
    default_subparsers = default_parser.add_subparsers(dest="parm_default_command", required=True)
    default_set_parser = default_subparsers.add_parser("set", help="Set a parameter-template default.")
    default_set_parser.add_argument("parm_path")
    default_set_parser.add_argument("--target", choices=("instance", "definition"), default="instance")
    default_source = default_set_parser.add_mutually_exclusive_group(required=True)
    default_source.add_argument("--current", action="store_true", help="Use the current parameter value.")
    default_source.add_argument("--value", help="JSON scalar or array.")
    default_set_parser.set_defaults(handler=handle_default_set)


def register_node_parms_parser(node_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parms_parser = node_subparsers.add_parser("parms", help="Discover parameters on one node.")
    parms_subparsers = parms_parser.add_subparsers(dest="node_parms_command", required=True)

    list_parser = parms_subparsers.add_parser("list", help="List parameters on one node.")
    list_parser.add_argument("node_path", help="Node path to inspect.")
    list_parser.add_argument("--name", help="Case-insensitive partial parm name match.")
    list_parser.add_argument("--template-type", dest="parm_type", help="Exact parm template type match.")
    list_parser.add_argument("--non-default", action="store_true", help="Only include non-default parameters.")
    list_parser.add_argument("--max-parms", type=int, default=100, help="Maximum parameters to return.")
    list_parser.add_argument(
        "--value-mode",
        choices=("none", "scalar", "summary"),
        help="Opt into metadata-only, scalar-only, or bounded-summary values.",
    )
    list_parser.add_argument(
        "--full-values",
        action="store_true",
        help="Do not truncate long string parameter values.",
    )
    list_parser.add_argument(
        "--values",
        action="store_true",
        help="Include parameter values and default flags. Kept for compatibility; values are always returned.",
    )
    list_parser.set_defaults(handler=handle_node_parms_list)

    find_parser = parms_subparsers.add_parser("find", help="Search parameters on one node.")
    find_parser.add_argument("node_path", help="Node path to inspect.")
    find_parser.add_argument("--name", help="Case-insensitive partial parm name match.")
    find_parser.add_argument("--type", "--template-type", dest="parm_type", help="Exact parm template type match.")
    find_parser.add_argument("--non-default", action="store_true", help="Only include non-default parameters.")
    find_parser.add_argument("--max-parms", type=int, default=100, help="Maximum parameters to return.")
    find_parser.add_argument(
        "--value-mode",
        choices=("none", "scalar", "summary"),
        help="Opt into metadata-only, scalar-only, or bounded-summary values.",
    )
    find_parser.add_argument(
        "--full-values",
        action="store_true",
        help="Do not truncate long string parameter values.",
    )
    find_parser.add_argument(
        "--values",
        action="store_true",
        help="Include parameter values and default flags. Kept for compatibility; values are always returned.",
    )
    find_parser.set_defaults(handler=handle_node_parms_find)
