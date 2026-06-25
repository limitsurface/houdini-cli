"""HDA creation, packaging, and lifecycle commands."""

from __future__ import annotations

import argparse
import os
from typing import Any

from ..format.envelopes import error_result, success_result
from ..transport.rpyc import connect, localize
from .hda_common import definition_for_node, definition_summary, save_definition
from .hda_sections import tool_xml
from .hda_validate import validate_asset
from .node_common import get_node, node_summary


def _existing_definition(session: Any, library: str, type_name: str) -> Any | None:
    if not os.path.exists(library):
        return None
    for definition in session.hou.hda.definitionsInFile(library):
        if localize(definition.nodeType().name()) == type_name:
            return definition
    return None


def _create_asset(session: Any, args: argparse.Namespace) -> str:
    node = get_node(session, args.subnet_path)
    if node.type().definition() is not None:
        raise ValueError("Existing HDA instances cannot be used as new HDA shells")
    if not bool(localize(node.canCreateDigitalAsset())):
        raise ValueError(f"Node cannot create a digital asset: {args.subnet_path}")
    library = os.path.abspath(os.path.expandvars(args.library))
    if args.create_dirs:
        os.makedirs(os.path.dirname(library), exist_ok=True)
    existing = _existing_definition(session, library, args.type_name)
    if existing and args.on_existing == "error":
        raise ValueError(f"Definition already exists: {args.type_name}")
    if existing and args.on_existing == "update":
        existing.updateFromNode(node)
        existing.save(library)
        node.changeNodeType(args.type_name)
        return args.subnet_path
    if existing and args.on_existing == "replace":
        existing.destroy()
    try:
        node.createDigitalAsset(
            name=args.type_name,
            hda_file_name=library,
            description=args.label,
            min_num_inputs=args.min_inputs,
            max_num_inputs=args.max_inputs,
            comment=args.comment,
            version=args.definition_version,
            create_backup=args.create_backup,
        )
    except EOFError:
        pass
    return args.subnet_path


def _create_asset_phase(args: argparse.Namespace) -> str:
    try:
        with connect(args.host, args.port) as session:
            return _create_asset(session, args)
    except EOFError:
        return args.subnet_path


def _created_asset(session: Any, node_path: str, type_name: str) -> Any:
    asset = get_node(session, node_path)
    actual_type = localize(asset.type().name())
    if actual_type != type_name:
        raise RuntimeError(
            f"HDA conversion did not produce the requested type: {actual_type} != {type_name}"
        )
    return asset


def _apply_creation_metadata(definition: Any, args: argparse.Namespace) -> None:
    definition.setMinNumInputs(args.min_inputs)
    definition.setMaxNumInputs(args.max_inputs)
    if args.icon:
        definition.setIcon(args.icon)


def _apply_source_interface(definition: Any, asset: Any) -> None:
    definition.setParmTemplateGroup(asset.parmTemplateGroup())


def _post_package_validation(session: Any, asset: Any, args: argparse.Namespace) -> dict | None:
    if args.no_validate:
        return None
    try:
        result = validate_asset(session, asset, fresh=True, cook=True, frames=[])
        result.setdefault("ok", True)
        return result
    except Exception as exc:
        return {"ok": False, "error": error_result(exc)["error"]}


def handle_create(args: argparse.Namespace) -> dict:
    node_path = _create_asset_phase(args)
    with connect(args.host, args.port) as session:
        asset = _created_asset(session, node_path, args.type_name)
        definition = definition_for_node(asset)
        _apply_source_interface(definition, asset)
        _apply_creation_metadata(definition, args)
        save_definition(definition)
        return success_result(
            {"node": node_summary(asset), "definition": definition_summary(session, definition)}
        )


def handle_package(args: argparse.Namespace) -> dict:
    node_path = _create_asset_phase(args)
    with connect(args.host, args.port) as session:
        asset = _created_asset(session, node_path, args.type_name)
        definition = definition_for_node(asset)
        _apply_source_interface(definition, asset)
        _apply_creation_metadata(definition, args)
        if args.tab_submenu:
            category = localize(asset.type().category().name())
            definition.addSection("Tools.shelf", tool_xml(args.tab_submenu, category))
        if args.expanded_preview:
            asset.setGenericFlag(session.hou.nodeFlag.Compress, False)
            definition.addSection(
                "OnCreated",
                'import hou\nkwargs["node"].setGenericFlag(hou.nodeFlag.Compress, False)\n',
            )
            definition.setExtraFileOption("OnCreated/IsPython", True)
        save_definition(definition)
        asset.matchCurrentDefinition()
        validation = _post_package_validation(session, asset, args)
        return success_result(
            {
                "node": node_summary(asset),
                "definition": definition_summary(session, definition),
                "validation": validation,
            }
        )


def handle_save(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        definition = definition_for_node(get_node(session, args.asset_node))
        path = args.library or localize(definition.libraryFilePath())
        definition.save(path)
        return success_result({"asset_node": args.asset_node, "library": path, "saved": True})


def handle_instantiate(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        parent = get_node(session, args.parent)
        node = (
            parent.createNode(args.type_name, args.name)
            if args.name
            else parent.createNode(args.type_name)
        )
        if args.input:
            node.setInput(0, get_node(session, args.input))
        if args.expanded:
            node.setGenericFlag(session.hou.nodeFlag.Compress, False)
        return success_result(node_summary(node))


def handle_unlock(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.asset_node)
        definition_for_node(node)
        node.allowEditingOfContents(propagate=args.propagate)
        return success_result(
            {"asset_node": args.asset_node, "locked": bool(localize(node.isLockedHDA()))}
        )


def handle_match(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.asset_node)
        definition_for_node(node)
        if not args.force and not bool(localize(node.matchesCurrentDefinition())):
            raise ValueError("Instance differs from its definition; use --force to discard changes")
        node.matchCurrentDefinition()
        return success_result({"asset_node": args.asset_node, "matches": True, "locked": True})


def handle_install(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        session.hou.hda.installFile(args.library, force_use_assets=args.force)
        definitions = session.hou.hda.definitionsInFile(args.library)
        return success_result(
            {"library": args.library, "types": [localize(x.nodeType().name()) for x in definitions]}
        )


def handle_uninstall(args: argparse.Namespace) -> dict:
    if not args.force:
        raise ValueError("Uninstall requires --force")
    with connect(args.host, args.port) as session:
        definitions = session.hou.hda.definitionsInFile(args.library)
        types = [localize(x.nodeType().name()) for x in definitions]
        session.hou.hda.uninstallFile(args.library)
        return success_result({"library": args.library, "types": types, "uninstalled": True})


def handle_update(args: argparse.Namespace) -> dict:
    with connect(args.host, args.port) as session:
        node = get_node(session, args.asset_node)
        definition = definition_for_node(node)
        contents = args.contents or args.all or not any(
            (args.interface, args.sections, args.tools, args.all)
        )
        applied = []
        interface = node.parmTemplateGroup() if args.interface or args.all else None
        preserved_sections = {
            name: localize(section.contents())
            for name, section in definition.sections().items()
            if name not in {"Contents.gz", "DialogScript"}
        }
        if contents:
            definition.updateFromNode(node)
            applied.append("contents")
        if interface is not None:
            definition.setParmTemplateGroup(interface)
            applied.append("interface")
        if args.sections or args.all:
            for name, text in preserved_sections.items():
                definition.addSection(name, text)
            applied.append("sections")
        if args.tools or args.all:
            if "Tools.shelf" in preserved_sections:
                definition.addSection("Tools.shelf", preserved_sections["Tools.shelf"])
            applied.append("tools")
        library = None if args.no_save else save_definition(definition)
        if not args.no_match:
            node.matchCurrentDefinition()
        validation = (
            validate_asset(session, node, fresh=True, cook=True, frames=[])
            if args.validate or args.all
            else None
        )
        return success_result(
            {
                "asset_node": args.asset_node,
                "applied": applied,
                "library": library,
                "validation": validation,
            }
        )
