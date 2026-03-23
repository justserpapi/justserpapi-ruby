#!/usr/bin/env python3
"""Control plane for the JustSerpAPI Ruby SDK."""

from __future__ import annotations

import argparse
import copy
import filecmp
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "config" / "sdk-manifest.json"
RELEASE_TAG_PATTERN = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")
VERSION_PATTERN = re.compile(r'^\s*VERSION\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)
TEMPLATE_PATTERN = re.compile(r"{{\s*([A-Z0-9_]+)\s*}}")


SUCCESS_RESPONSE_DESCRIPTION = "Successful JustSerpAPI response."
UNEXPECTED_RESPONSE_DESCRIPTION = "Unexpected response."


class CLIError(RuntimeError):
    """Raised for user-facing control-plane errors."""


@dataclass
class BreakingChangeReport:
    removed_operations: List[str]
    removed_required_params: List[str]
    newly_required_params: List[str]

    def has_changes(self) -> bool:
        return bool(
            self.removed_operations
            or self.removed_required_params
            or self.newly_required_params
        )


def log(message: str) -> None:
    print(message, file=sys.stderr)


def load_manifest() -> Dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def resolve_path(relative_path: str) -> pathlib.Path:
    return ROOT / relative_path


def write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_json(path: pathlib.Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(command: Sequence[str], cwd: pathlib.Path = ROOT) -> None:
    subprocess.run(list(command), cwd=cwd, check=True)


def render_template(template: str, context: Dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise CLIError("Missing template value for %s" % key)
        return context[key]

    return TEMPLATE_PATTERN.sub(replace, template)


def render_template_file(template_path: pathlib.Path, output_path: pathlib.Path, context: Dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_template(template_path.read_text(encoding="utf-8"), context),
        encoding="utf-8",
    )


def load_package_version(version_path: pathlib.Path) -> str:
    content = version_path.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        raise CLIError("Unable to parse VERSION from %s" % version_path)
    return match.group(1)


def resolve_source_url(manifest: Dict[str, Any], explicit_url: Optional[str]) -> str:
    source_url = explicit_url or os.getenv("JUSTSERPAPI_OPENAPI_URL") or manifest["spec"]["source_url"]
    parsed = urlparse(source_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    has_api_key = any(key == "api_key" for key, _ in query)
    env_api_key = os.getenv("JUSTSERPAPI_OPENAPI_API_KEY")
    if env_api_key and not has_api_key:
        query.append(("api_key", env_api_key))
    return urlunparse(parsed._replace(query=urlencode(query)))


def fetch_spec_command(args: argparse.Namespace, manifest: Dict[str, Any]) -> None:
    source_url = resolve_source_url(manifest, args.source_url)
    output_path = resolve_path(args.output or manifest["spec"]["raw_path"])

    request = Request(
        source_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "justserpapi-ruby-sdkctl/0.1"
        },
    )

    log("Fetching spec from %s" % source_url)
    try:
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 401:
            raise CLIError(
                "Spec fetch returned HTTP 401. Set JUSTSERPAPI_OPENAPI_API_KEY or JUSTSERPAPI_OPENAPI_URL."
            ) from exc
        raise CLIError("Unable to fetch spec from %s: HTTP %s" % (source_url, exc.code)) from exc
    except URLError as exc:
        raise CLIError("Unable to fetch spec from %s: %s" % (source_url, exc)) from exc

    write_text(output_path, json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    log("Wrote raw spec to %s" % output_path)


def build_success_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "description": "Standard JustSerpAPI response envelope.",
        "required": ["code", "message", "data", "requestId", "timestamp"],
        "properties": {
            "code": {
                "type": "integer",
                "format": "int32",
                "description": "Application-level status code.",
            },
            "message": {
                "type": "string",
                "description": "Response message.",
            },
            "data": {
                "type": "object",
                "description": "Endpoint-specific payload.",
                "additionalProperties": True,
            },
            "requestId": {
                "type": "string",
                "description": "Server-generated request identifier.",
            },
            "timestamp": {
                "type": "integer",
                "format": "int64",
                "description": "Server timestamp in epoch milliseconds.",
            },
        },
    }


def build_security_schemes() -> Dict[str, Any]:
    return {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Primary authentication header for JustSerpAPI.",
        },
        "ApiKeyQuery": {
            "type": "apiKey",
            "in": "query",
            "name": "api_key",
            "description": "Compatibility fallback query parameter for JustSerpAPI.",
        },
    }


def normalize_operation(operation: Dict[str, Any]) -> Dict[str, Any]:
    normalized = copy.deepcopy(operation)
    normalized["tags"] = ["Google"]

    responses = normalized.setdefault("responses", {})
    default_response = responses.get("default", {})
    json_content = default_response.get("content", {}).get("application/json", {})
    examples = copy.deepcopy(json_content.get("examples", {}))

    success_response = {
        "description": SUCCESS_RESPONSE_DESCRIPTION,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/JustSerpApiResponse"}
            }
        },
    }
    if examples:
        success_response["content"]["application/json"]["examples"] = examples

    responses["200"] = success_response
    responses["default"] = {"description": UNEXPECTED_RESPONSE_DESCRIPTION}
    normalized["security"] = [{"ApiKeyAuth": [], "ApiKeyQuery": []}]
    return normalized


def normalize_spec(document: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    normalized = copy.deepcopy(document)
    normalized["openapi"] = "3.0.3"
    normalized["servers"] = [
        {
            "url": manifest["service"]["default_server_url"],
            "description": "JustSerpAPI production server",
        }
    ]
    normalized["tags"] = [
        {
            "name": "Google",
            "description": "Google search and discovery endpoints.",
        }
    ]
    normalized["security"] = [{"ApiKeyAuth": [], "ApiKeyQuery": []}]

    components = normalized.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas["JustSerpApiResponse"] = build_success_schema()

    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes.update(build_security_schemes())

    paths = normalized.get("paths", {})
    for methods in paths.values():
        for method_name, operation in list(methods.items()):
            if isinstance(operation, dict):
                methods[method_name] = normalize_operation(operation)
    return normalized


def normalize_spec_command(args: argparse.Namespace, manifest: Dict[str, Any]) -> None:
    input_path = resolve_path(args.input or manifest["spec"]["raw_path"])
    output_path = resolve_path(args.output or manifest["spec"]["normalized_path"])
    normalized = normalize_spec(load_json(input_path), manifest)
    write_text(output_path, json.dumps(normalized, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    log("Wrote normalized spec to %s" % output_path)


def ensure_generator_cli(version: str, cache_dir: pathlib.Path) -> pathlib.Path:
    jar_path = cache_dir / ("openapi-generator-cli-%s.jar" % version)
    if jar_path.exists():
        return jar_path

    cache_dir.mkdir(parents=True, exist_ok=True)
    download_url = (
        "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/"
        "%s/openapi-generator-cli-%s.jar" % (version, version)
    )
    request = Request(download_url, headers={"User-Agent": "justserpapi-ruby-sdkctl/0.1"})
    log("Downloading OpenAPI Generator %s" % version)
    try:
        with urlopen(request) as response:
            jar_path.write_bytes(response.read())
    except (HTTPError, URLError) as exc:
        raise CLIError("Unable to download OpenAPI Generator %s: %s" % (version, exc)) from exc
    return jar_path


def generation_context(manifest: Dict[str, Any], package_version: str) -> Dict[str, str]:
    package = manifest["package"]
    return {
        "PACKAGE_NAME": str(package["name"]),
        "MODULE_NAME": str(package["module_name"]),
        "PACKAGE_VERSION": str(package_version),
        "PACKAGE_SUMMARY": str(package["summary"]),
        "PACKAGE_DESCRIPTION": str(package["description"]),
        "PACKAGE_LICENSE": str(package["license"]),
        "PACKAGE_REQUIRED_RUBY_VERSION": str(package["required_ruby_version"]),
        "REPO_REMOTE": str(package["repo_remote"]),
    }


def generate_command(args: argparse.Namespace, manifest: Dict[str, Any]) -> pathlib.Path:
    generator = manifest["generator"]
    spec_path = resolve_path(args.spec or manifest["spec"]["normalized_path"])
    workspace = resolve_path(args.workspace or manifest["generate"]["workspace"])
    output_dir = workspace / manifest["generate"]["output_subdir"]
    version_file = resolve_path(manifest["package"]["version_file"])
    package_version = load_package_version(version_file)
    jar_path = ensure_generator_cli(generator["version"], resolve_path(generator["cache_dir"]))

    if args.clean and workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="justserpapi-ruby-config-") as temp_dir_name:
        temp_dir = pathlib.Path(temp_dir_name)
        rendered_config_path = temp_dir / "ruby-config.json"
        render_template_file(
            resolve_path(generator["config_template"]),
            rendered_config_path,
            generation_context(manifest, package_version),
        )

        command = [
            "java",
            "-jar",
            str(jar_path),
            "generate",
            "-g",
            "ruby",
            "-i",
            str(spec_path),
            "-o",
            str(output_dir),
            "-c",
            str(rendered_config_path),
            "--global-property",
            "apiDocs=false,modelDocs=false,apiTests=false,modelTests=false",
        ]
        run(command)
    log("Generated Ruby SDK workspace under %s" % output_dir)
    return output_dir


def compare_directories(left: pathlib.Path, right: pathlib.Path) -> bool:
    comparison = filecmp.dircmp(left, right)
    if comparison.left_only or comparison.right_only or comparison.diff_files or comparison.funny_files:
        return False
    return all(compare_directories(left / subdir, right / subdir) for subdir in comparison.common_dirs)


def sync_runtime(output_dir: pathlib.Path, runtime_dir: pathlib.Path, check: bool) -> None:
    generated_runtime = output_dir / "lib"
    if not generated_runtime.exists():
        raise CLIError("Expected generated runtime under %s" % generated_runtime)

    if check:
        if not runtime_dir.exists():
            raise CLIError("Missing committed generated runtime directory: %s" % runtime_dir)
        if not compare_directories(generated_runtime, runtime_dir):
            raise CLIError("Generated runtime is out of date. Run `python3 scripts/sdkctl.py sync`.")
        return

    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(generated_runtime, runtime_dir)
    log("Synced generated runtime into %s" % runtime_dir)


def sync_command(args: argparse.Namespace, manifest: Dict[str, Any]) -> None:
    if not args.skip_fetch:
        fetch_spec_command(
            argparse.Namespace(
                source_url=args.source_url,
                output=manifest["spec"]["raw_path"],
            ),
            manifest,
        )
    normalize_spec_command(
        argparse.Namespace(
            input=manifest["spec"]["raw_path"],
            output=manifest["spec"]["normalized_path"],
        ),
        manifest,
    )
    output_dir = generate_command(
        argparse.Namespace(
            spec=manifest["spec"]["normalized_path"],
            workspace=args.workspace,
            clean=True,
        ),
        manifest,
    )
    sync_runtime(output_dir, resolve_path(manifest["generate"]["runtime_dir"]), args.check)


def parse_release_tag(raw_tag: str) -> str:
    match = RELEASE_TAG_PATTERN.match(raw_tag)
    if not match:
        raise CLIError("Release tag must match vX.Y.Z, found %r." % raw_tag)
    return match.group("version")


def verify_release_command(args: argparse.Namespace, manifest: Dict[str, Any]) -> None:
    raw_tag = args.tag or os.getenv("GITHUB_REF_NAME")
    if not raw_tag:
        raise CLIError("Release tag is required. Pass --tag or set GITHUB_REF_NAME.")

    release_version = parse_release_tag(raw_tag)
    package_version = load_package_version(resolve_path(manifest["package"]["version_file"]))
    if release_version != package_version:
        raise CLIError(
            "Release tag version %s does not match package version %s."
            % (release_version, package_version)
        )
    log("Release verification passed for %s" % raw_tag)


def normalize_param_signature(param: Dict[str, Any]) -> Tuple[str, str]:
    return str(param.get("in")), str(param.get("name"))


def required_query_params(operation: Dict[str, Any], path_item: Dict[str, Any]) -> List[Tuple[str, str]]:
    params = []
    for source in (path_item.get("parameters", []), operation.get("parameters", [])):
        for param in source:
            if not isinstance(param, dict):
                continue
            if param.get("in") != "query":
                continue
            if not param.get("required"):
                continue
            params.append(normalize_param_signature(param))
    return sorted(set(params))


def operation_map(spec: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    mapping: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if isinstance(operation, dict):
                mapping[(method.lower(), path)] = {
                    "operation": operation,
                    "path_item": path_item,
                }
    return mapping


def detect_breaking_changes(baseline: Dict[str, Any], current: Dict[str, Any]) -> BreakingChangeReport:
    baseline_map = operation_map(baseline)
    current_map = operation_map(current)
    removed_operations = []
    removed_required_params = []
    newly_required_params = []

    for key, baseline_entry in baseline_map.items():
        if key not in current_map:
            removed_operations.append("%s %s" % (key[0].upper(), key[1]))
            continue

        current_entry = current_map[key]
        baseline_required = set(required_query_params(baseline_entry["operation"], baseline_entry["path_item"]))
        current_required = set(required_query_params(current_entry["operation"], current_entry["path_item"]))
        for scope, name in sorted(baseline_required - current_required):
            removed_required_params.append("%s %s removed required %s param %s" % (key[0].upper(), key[1], scope, name))
        for scope, name in sorted(current_required - baseline_required):
            newly_required_params.append("%s %s added required %s param %s" % (key[0].upper(), key[1], scope, name))

    return BreakingChangeReport(
        removed_operations=removed_operations,
        removed_required_params=removed_required_params,
        newly_required_params=newly_required_params,
    )


def breaking_check_command(args: argparse.Namespace, manifest: Dict[str, Any]) -> None:
    baseline_path = resolve_path(args.baseline or manifest["spec"]["baseline_path"])
    current_path = resolve_path(args.current or manifest["spec"]["normalized_path"])
    if not baseline_path.exists():
        raise CLIError("Baseline spec not found: %s" % baseline_path)
    if not current_path.exists():
        raise CLIError("Current normalized spec not found: %s" % current_path)

    report = detect_breaking_changes(load_json(baseline_path), load_json(current_path))
    if report.has_changes():
        for line in report.removed_operations + report.removed_required_params + report.newly_required_params:
            log("breaking: %s" % line)
        raise CLIError("Breaking changes detected between %s and %s." % (baseline_path, current_path))
    log("No breaking changes detected between %s and %s." % (baseline_path, current_path))


def promote_baseline_command(args: argparse.Namespace, manifest: Dict[str, Any]) -> None:
    normalized_path = resolve_path(args.normalized or manifest["spec"]["normalized_path"])
    baseline_path = resolve_path(args.baseline or manifest["spec"]["baseline_path"])
    if not normalized_path.exists():
        raise CLIError("Normalized spec not found: %s" % normalized_path)
    write_text(baseline_path, normalized_path.read_text(encoding="utf-8"))
    log("Updated baseline spec at %s" % baseline_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JustSerpAPI Ruby SDK control plane.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch-spec", help="Fetch the upstream OpenAPI spec.")
    fetch_parser.add_argument("--source-url", help="Override spec source URL.")
    fetch_parser.add_argument("--output", help="Output path relative to repo root.")

    normalize_parser = subparsers.add_parser("normalize-spec", help="Normalize the raw spec for code generation.")
    normalize_parser.add_argument("--input", help="Input path relative to repo root.")
    normalize_parser.add_argument("--output", help="Output path relative to repo root.")

    generate_parser = subparsers.add_parser("generate", help="Generate the Ruby SDK into the workspace.")
    generate_parser.add_argument("--spec", help="Normalized spec path relative to repo root.")
    generate_parser.add_argument("--workspace", help="Generation workspace relative to repo root.")
    generate_parser.add_argument("--clean", action="store_true", help="Delete the generation workspace before generating.")

    sync_parser = subparsers.add_parser("sync", help="Fetch, normalize, generate, and sync the committed runtime.")
    sync_parser.add_argument("--skip-fetch", action="store_true", help="Reuse the checked-in raw spec.")
    sync_parser.add_argument("--check", action="store_true", help="Verify the committed generated runtime is up to date.")
    sync_parser.add_argument("--workspace", help="Generation workspace relative to repo root.")
    sync_parser.add_argument("--source-url", help="Override spec source URL.")

    release_parser = subparsers.add_parser("verify-release", help="Verify that the release tag matches the gem version.")
    release_parser.add_argument("--tag", help="Release tag in the form vX.Y.Z.")

    breaking_parser = subparsers.add_parser("breaking-check", help="Compare baseline and normalized specs for breaking changes.")
    breaking_parser.add_argument("--baseline", help="Baseline spec path relative to repo root.")
    breaking_parser.add_argument("--current", help="Current normalized spec path relative to repo root.")

    baseline_parser = subparsers.add_parser("promote-baseline", help="Copy the normalized spec into the baseline slot.")
    baseline_parser.add_argument("--normalized", help="Normalized spec path relative to repo root.")
    baseline_parser.add_argument("--baseline", help="Baseline output path relative to repo root.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = load_manifest()
    try:
        if args.command == "fetch-spec":
            fetch_spec_command(args, manifest)
        elif args.command == "normalize-spec":
            normalize_spec_command(args, manifest)
        elif args.command == "generate":
            generate_command(args, manifest)
        elif args.command == "sync":
            sync_command(args, manifest)
        elif args.command == "verify-release":
            verify_release_command(args, manifest)
        elif args.command == "breaking-check":
            breaking_check_command(args, manifest)
        elif args.command == "promote-baseline":
            promote_baseline_command(args, manifest)
        else:
            parser.error("Unknown command %s" % args.command)
    except CLIError as exc:
        log("error: %s" % exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

