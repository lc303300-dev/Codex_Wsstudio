#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import json
import math
import os
import re
import ssl
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


DEFAULT_SOURCES = (
    "github",
    "npm",
    "mcp",
    "glama",
    "agentskill",
    "skillsmp",
    "clawhub",
    "skillssh",
    "vscode",
    "openvsx",
    "web",
    "smithery",
    "pulsemcp",
)

CHINESE_SYNONYMS = {
    "飞书": ("feishu", "lark"),
    "飞书机器人": ("feishu bot", "lark bot"),
    "机器人": ("bot", "chatbot", "messenger"),
    "命令": ("control", "command", "remote control"),
    "控制": ("control", "remote control"),
    "遥控": ("remote control", "control"),
    "桥": ("bridge", "connector"),
    "桥接": ("bridge", "connector", "integration"),
    "连接": ("bridge", "connector", "integration"),
    "自我进化": ("self improving", "self evolving", "darwin", "optimization"),
    "进化": ("evolving", "darwin", "optimization"),
    "工具": ("tool", "software", "utility"),
    "插件": ("plugin", "extension"),
    "技能": ("skill", "agent skill"),
}

ENGLISH_SYNONYMS = {
    "feishu": ("feishu", "lark"),
    "lark": ("lark", "feishu"),
    "bot": ("bot", "chatbot", "messenger"),
    "bridge": ("bridge", "connector", "integration"),
    "control": ("control", "remote control", "command"),
    "remote": ("remote", "remote control"),
    "skill": ("skill", "agent skill", "claude skill"),
    "mcp": ("mcp", "mcp server", "model context protocol"),
    "extension": ("extension", "plugin", "vs code extension"),
}

SOURCE_LABELS = {
    "github": "GitHub repo",
    "npm": "npm package",
    "mcp": "MCP server",
    "glama": "MCP server",
    "agentskill": "Agent Skill",
    "skillsmp": "Agent Skill marketplace",
    "clawhub": "Community Agent Skill marketplace",
    "skillssh": "skills.sh Agent Skill",
    "vscode": "VS Code extension",
    "openvsx": "Open VSX extension",
    "web": "web result",
    "smithery": "MCP server",
    "pulsemcp": "MCP server",
}

NATIVE_FEATURE_CHECKLIST = (
    "official documentation and help center",
    "current product UI: selected text, right-click/context menu, hover menu, toolbar",
    "command palette, slash commands, and keyboard shortcuts",
    "extension/plugin/API support and built-in integrations",
    "release notes and changelog for recently shipped native features",
)

PRODUCT_PATTERNS = (
    ("codex desktop", "Codex Desktop"),
    ("codex app", "Codex Desktop"),
    ("codex cli", "Codex CLI"),
    ("openai codex", "OpenAI Codex"),
    ("chatgpt desktop", "ChatGPT Desktop"),
    ("chatgpt", "ChatGPT"),
    ("claude code", "Claude Code"),
    ("claude desktop", "Claude Desktop"),
    ("cursor", "Cursor"),
    ("vscode", "VS Code"),
    ("vs code", "VS Code"),
    ("raycast", "Raycast"),
    ("feishu", "Feishu/Lark"),
    ("lark", "Feishu/Lark"),
)


@dataclass
class NeedProfile:
    raw: str
    normalized_goal: str
    positive_terms: set[str]
    hard_terms: set[str]
    negative_patterns: tuple[str, ...] = ()
    required_groups: tuple[tuple[str, ...], ...] = ()


@dataclass
class QueryPlan:
    raw: str
    profile: NeedProfile
    queries: list[str]
    native_audit_queries: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    name: str
    kind: str
    source: str
    url: str
    description: str = ""
    evidence: str = ""
    install_hint: str = ""
    stars: int | None = None
    forks: int | None = None
    downloads: int | None = None
    rating: float | None = None
    updated_at: str | None = None
    license: str | None = None
    archived: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
    sources: set[str] = field(default_factory=set)
    v0: bool = False
    v1: bool = False
    rejected_reason: str = ""
    score: float = 0.0
    goal_match: float = 0.0
    evidence_strength: float = 0.0
    project_quality: float = 0.0
    landing_friction: float = 0.0
    multi_source: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.sources.add(self.source)

    @property
    def search_text(self) -> str:
        return normalize_text(
            " ".join(
                part
                for part in (
                    self.name,
                    self.kind,
                    self.description,
                    self.evidence,
                    self.install_hint,
                    self.license or "",
                    " ".join(self.sources),
                )
                if part
            )
        )


def normalize_text(text: str) -> str:
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def compact(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def unique_keep_order(items: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        item = re.sub(r"\s+", " ", item).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if limit is not None and len(result) >= limit:
            break
    return result


def extract_terms(raw: str) -> set[str]:
    normalized = normalize_text(raw)
    terms: set[str] = set(re.findall(r"[a-z][a-z0-9+.#-]*", normalized))

    for cn, synonyms in CHINESE_SYNONYMS.items():
        if cn in raw:
            for synonym in synonyms:
                terms.update(synonym.split())
                terms.add(synonym)

    for word, synonyms in ENGLISH_SYNONYMS.items():
        if word in normalized:
            for synonym in synonyms:
                terms.update(synonym.split())
                terms.add(synonym)

    if "claude code" in normalized or ("claude" in terms and "code" in terms):
        terms.add("claude code")
    if "codex" in normalized:
        terms.add("codex")
    if "vscode" in normalized or "vs code" in normalized:
        terms.update({"vscode", "vs code", "extension"})
    if "mcp" in normalized:
        terms.update({"mcp", "mcp server", "model context protocol"})
    return {term for term in terms if len(term) > 1}


def build_need_profile(raw: str) -> NeedProfile:
    terms = extract_terms(raw)
    normalized = normalize_text(raw)
    hard_terms: set[str] = set()
    required_groups: list[tuple[str, ...]] = []

    if "飞书" in raw or "feishu" in normalized or "lark" in normalized:
        hard_terms.update({"feishu", "lark"})
        required_groups.append(("feishu", "lark"))
    if "claude code" in normalized:
        hard_terms.update({"claude", "code"})
        required_groups.append(("claude code",))
    elif "claude" in normalized:
        hard_terms.add("claude")
        required_groups.append(("claude",))
    if "codex" in normalized:
        hard_terms.add("codex")
        required_groups.append(("codex",))
    if "darwin" in normalized or "达尔文" in raw:
        hard_terms.add("darwin")
        required_groups.append(("darwin", "darwin skill", "darwin-skill"))
    if "mcp" in normalized:
        hard_terms.add("mcp")
        required_groups.append(("mcp", "model context protocol"))
    if "skill" in normalized or "技能" in raw:
        hard_terms.add("skill")

    negative_patterns: list[str] = []
    if ("飞书" in raw or "feishu" in normalized or "lark" in normalized) and (
        "claude" in normalized
    ):
        # The common false positive is the opposite direction: Claude operates Feishu.
        negative_patterns.extend(
            [
                "claude controls feishu",
                "claude operates feishu",
                "claude creates feishu",
                "claude reads feishu",
                "claude write feishu",
                "claude writes feishu",
            ]
        )

    return NeedProfile(
        raw=raw,
        normalized_goal=raw.strip(),
        positive_terms=terms,
        hard_terms=hard_terms or terms,
        negative_patterns=tuple(negative_patterns),
        required_groups=tuple(required_groups),
    )


def detect_target_products(raw: str) -> list[str]:
    normalized = normalize_text(raw)
    products: list[str] = []
    for pattern, product in PRODUCT_PATTERNS:
        if pattern in normalized:
            products.append(product)
    if "codex" in normalized and "桌面" in raw:
        products.append("Codex Desktop")
    if "chatgpt" in normalized and "桌面" in raw:
        products.append("ChatGPT Desktop")
    return unique_keep_order(products, 3)


def needs_native_feature_audit(raw: str) -> bool:
    normalized = normalize_text(raw)
    product_signals = bool(detect_target_products(raw))
    helper_signals = any(
        signal in normalized
        for signal in (
            "extension",
            "plugin",
            "overlay",
            "desktop",
            "cli",
            "integration",
            "helper",
            "assistant",
            "workflow",
            "automation",
            "right click",
            "context menu",
            "keyboard shortcut",
            "shortcut",
            "command palette",
            "selected text",
            "selection",
            "native",
            "built in",
            "built-in",
        )
    ) or any(
        signal in raw
        for signal in (
            "插件",
            "扩展",
            "桌面",
            "命令",
            "命令行",
            "集成",
            "辅助",
            "自动化",
            "控制",
            "桥接",
            "右键",
            "菜单",
            "快捷键",
            "命令面板",
            "选中",
            "划线",
            "原生",
            "内置",
        )
    )
    return product_signals and helper_signals


def build_native_audit_queries(raw: str, max_queries: int = 6) -> list[str]:
    if not needs_native_feature_audit(raw):
        return []

    products = detect_target_products(raw)
    if not products:
        return []

    capability = normalize_text(raw)
    capability = re.sub(
        r"\b(find|tool|software|extension|plugin|helper|assistant|for|to|that|can|with)\b",
        " ",
        capability,
    )
    capability = re.sub(r"\s+", " ", capability).strip()
    capability_terms = " ".join(capability.split()[:8])

    queries: list[str] = []
    for product in products:
        queries.extend(
            [
                f"{product} official docs {capability_terms}".strip(),
                f"{product} built-in native feature selected text context menu shortcut",
                f"{product} command palette keyboard shortcuts selected text",
                f"{product} extension plugin API custom commands",
                f"{product} release notes {capability_terms}".strip(),
            ]
        )
    return unique_keep_order(queries, max_queries)


def build_query_plan(raw: str, max_queries: int = 12) -> QueryPlan:
    profile = build_need_profile(raw)
    native_audit_queries = build_native_audit_queries(raw)
    normalized = normalize_text(raw)
    terms = profile.positive_terms
    queries: list[str] = [raw.strip()]

    has_feishu = any(term in terms for term in ("feishu", "lark"))
    has_claude_code = "claude code" in terms or ("claude" in terms and "code" in terms)
    has_codex = "codex" in terms
    has_evolving = any(term in terms for term in ("darwin", "self improving", "self evolving"))

    if has_feishu and has_claude_code:
        queries.extend(
            [
                '"Feishu" "Claude Code" bridge',
                '"Lark" "Claude Code" bridge',
                "feishu claude code bot",
                "lark claude code cli bridge",
                "claude code feishu bridge",
                "claude code feishu vscode extension",
                "claude code feishu skill",
                "claude code feishu mcp",
                "claude code feishu npm",
            ]
        )
    elif has_feishu and has_codex:
        queries.extend(
            [
                '"Feishu" Codex bridge',
                '"Lark" Codex bridge',
                "feishu codex bot",
                "codex feishu skill",
                "codex feishu mcp",
            ]
        )
    elif has_evolving:
        queries.extend(
            [
                '"Darwin Skill"',
                "darwin-skill",
                "self improving agent skill",
                "self evolving skill darwin",
                "darwin skill claude code",
                "agent skill optimization",
                "skill evolution claude code",
            ]
        )
    else:
        base_terms = [term for term in terms if len(term.split()) == 1]
        if base_terms:
            base = " ".join(base_terms[:6])
            queries.extend(
                [
                    f"{base} tool",
                    f"{base} github",
                    f"{base} mcp server",
                    f"{base} agent skill",
                    f"{base} npm package",
                    f"{base} vscode extension",
                ]
            )

    queries.extend(
        [
            f"{raw} GitHub",
            f"{raw} MCP",
            f"{raw} Skill",
            f"{raw} VS Code extension",
        ]
    )

    if normalized != raw.strip().lower():
        queries.append(normalized)

    return QueryPlan(
        raw=raw,
        profile=profile,
        queries=unique_keep_order(queries, max_queries),
        native_audit_queries=native_audit_queries,
    )


def request_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": "tool-scout-skill/0.1",
        "Accept": "application/json,text/plain,*/*",
    }
    if extra:
        headers.update(extra)
    return headers


def http_get_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 8,
) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers=request_headers(headers))
    with urlopen_with_cert_fallback(req, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        return response.status, response.read(), content_type


def http_get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 8,
) -> Any:
    _, body, _ = http_get_bytes(url, headers=headers, timeout=timeout)
    return json.loads(body.decode("utf-8", errors="replace"))


def http_get_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 8,
) -> str:
    _, body, _ = http_get_bytes(url, headers=headers, timeout=timeout)
    return body.decode("utf-8", errors="replace")


def http_post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 8,
) -> Any:
    body = json.dumps(payload).encode("utf-8")
    merged_headers = request_headers({"Content-Type": "application/json"})
    if headers:
        merged_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=merged_headers, method="POST")
    with urlopen_with_cert_fallback(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def urlopen_with_cert_fallback(req: urllib.request.Request, timeout: float) -> Any:
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as exc:
        if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError) or (
            "CERTIFICATE_VERIFY_FAILED" in str(exc)
        ):
            insecure_context = ssl._create_unverified_context()  # noqa: S323
            return urllib.request.urlopen(req, timeout=timeout, context=insecure_context)
        raise


async def safe_call(label: str, coro: Any) -> list[Candidate]:
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001 - searchers must fail soft.
        print(f"[warn] {label} searcher failed: {exc}", file=sys.stderr)
        return []


def source_queries(plan: QueryPlan, count: int = 5) -> list[str]:
    return plan.queries[:count]


def strip_search_operators(query: str) -> str:
    query = query.replace('"', " ")
    query = re.sub(r"\b(in|sort|repo|language|topic):\S+", " ", query)
    return re.sub(r"\s+", " ", query).strip()


async def search_github(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    token = get_github_token()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    candidates: dict[str, Candidate] = {}
    per_page = min(max_results, 10)

    request_specs: list[dict[str, str | int]] = []
    for query in source_queries(plan, 6):
        q = f"{query} in:name,description,readme"
        request_specs.append({"q": q, "per_page": per_page})
    for query in source_queries(plan, 3):
        q = f"{query} in:name,description,readme"
        request_specs.append({"q": q, "sort": "updated", "order": "desc", "per_page": per_page})

    for spec in request_specs:
        params = urllib.parse.urlencode(spec)
        url = f"https://api.github.com/search/repositories?{params}"
        try:
            data = await asyncio.to_thread(http_get_json, url, headers=headers, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in {403, 422}:
                continue
            raise
        for item in data.get("items", [])[:per_page]:
            html_url = item.get("html_url") or ""
            if not html_url:
                continue
            candidate = Candidate(
                name=item.get("full_name") or item.get("name") or html_url,
                kind="GitHub repo",
                source="github",
                url=html_url,
                description=item.get("description") or "",
                stars=item.get("stargazers_count"),
                forks=item.get("forks_count"),
                updated_at=item.get("updated_at"),
                license=(item.get("license") or {}).get("spdx_id"),
                archived=bool(item.get("archived")),
                raw={
                    "language": item.get("language"),
                    "topics": item.get("topics", []),
                    "default_branch": item.get("default_branch"),
                },
            )
            candidates.setdefault(html_url.lower(), candidate)

    # Pull README snippets for top GitHub candidates so V1 is not description-only.
    top_for_readme = sorted(
        candidates.values(), key=lambda c: (c.stars or 0, c.updated_at or ""), reverse=True
    )[: min(6, len(candidates))]
    await asyncio.gather(
        *[hydrate_github_readme(candidate, timeout=timeout) for candidate in top_for_readme],
        return_exceptions=True,
    )
    return list(candidates.values())


def get_github_token() -> str | None:
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


async def hydrate_github_readme(candidate: Candidate, timeout: float) -> None:
    match = re.match(r"https://github\.com/([^/]+/[^/]+)", candidate.url)
    if not match:
        return
    full_name = match.group(1)
    branch = candidate.raw.get("default_branch") or "main"
    raw_url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
    try:
        text = await asyncio.to_thread(http_get_text, raw_url, timeout=timeout)
    except Exception:
        api_url = f"https://api.github.com/repos/{full_name}/readme"
        token = os.getenv("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            data = await asyncio.to_thread(http_get_json, api_url, headers=headers, timeout=timeout)
            encoded = data.get("content", "")
            text = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except Exception:
            return
    candidate.evidence = compact(text, 4000)


async def search_npm(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}
    for query in source_queries(plan, 5):
        text = strip_search_operators(query)
        params = urllib.parse.urlencode({"text": text, "size": min(max_results, 10)})
        url = f"https://registry.npmjs.org/-/v1/search?{params}"
        data = await asyncio.to_thread(http_get_json, url, timeout=timeout)
        for obj in data.get("objects", []):
            package = obj.get("package", {})
            name = package.get("name")
            if not name:
                continue
            links = package.get("links") or {}
            candidate_url = links.get("repository") or links.get("npm") or f"https://www.npmjs.com/package/{name}"
            keywords = " ".join(package.get("keywords") or [])
            detail = obj.get("score", {}).get("detail", {})
            candidate = Candidate(
                name=name,
                kind="npm package",
                source="npm",
                url=candidate_url,
                description=package.get("description") or "",
                evidence=keywords,
                downloads=(obj.get("downloads") or {}).get("monthly")
                or (obj.get("downloads") or {}).get("weekly"),
                updated_at=obj.get("updated") or package.get("date"),
                license=package.get("license"),
                raw={
                    "version": package.get("version"),
                    "npm": links.get("npm"),
                    "repository": links.get("repository"),
                    "quality": detail.get("quality"),
                    "popularity": detail.get("popularity"),
                    "maintenance": detail.get("maintenance"),
                },
            )
            candidates.setdefault(f"npm:{name}".lower(), candidate)
    return list(candidates.values())


async def search_official_mcp(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}
    for query in source_queries(plan, 4):
        params = urllib.parse.urlencode({"search": strip_search_operators(query), "limit": max_results})
        url = f"https://registry.modelcontextprotocol.io/v0/servers?{params}"
        data = await asyncio.to_thread(http_get_json, url, timeout=timeout)
        for entry in data.get("servers", []):
            server = entry.get("server", entry)
            name = server.get("name") or server.get("id")
            if not name:
                continue
            repository = server.get("repository") or {}
            packages = server.get("packages") or []
            package_hint = " ".join(
                str(pkg.get("identifier") or pkg.get("registryType") or "") for pkg in packages
            )
            candidate = Candidate(
                name=name,
                kind="MCP server",
                source="mcp",
                url=repository.get("url") or server.get("websiteUrl") or server.get("url") or "",
                description=server.get("description") or "",
                evidence=package_hint,
                updated_at=server.get("updatedAt") or server.get("publishedAt"),
                license=server.get("license"),
                raw={"version": server.get("version"), "packages": packages},
            )
            if candidate.url:
                candidates.setdefault(candidate.url.lower(), candidate)
            else:
                candidates.setdefault(f"mcp:{name}".lower(), candidate)
    return list(candidates.values())


async def search_glama(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}
    for query in source_queries(plan, 4):
        params = urllib.parse.urlencode({"query": strip_search_operators(query), "limit": max_results})
        url = f"https://glama.ai/api/mcp/v1/servers?{params}"
        data = await asyncio.to_thread(http_get_json, url, timeout=timeout)
        for server in data.get("servers", []):
            name = server.get("name") or server.get("slug") or server.get("id")
            if not name:
                continue
            repository = server.get("repository") or {}
            tools = server.get("tools") or []
            tool_names = " ".join(tool.get("name", "") for tool in tools if isinstance(tool, dict))
            license_info = server.get("spdxLicense") or {}
            candidate = Candidate(
                name=f"{server.get('namespace')}/{name}" if server.get("namespace") else name,
                kind="MCP server",
                source="glama",
                url=repository.get("url") or server.get("url") or "",
                description=server.get("description") or "",
                evidence=tool_names,
                updated_at=server.get("updatedAt") or server.get("createdAt"),
                license=license_info.get("name") if isinstance(license_info, dict) else None,
                raw={"attributes": server.get("attributes"), "slug": server.get("slug")},
            )
            key = (candidate.url or f"glama:{name}").lower()
            candidates.setdefault(key, candidate)
    return list(candidates.values())


async def search_agentskill(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}

    for query in source_queries(plan, 4):
        params = urllib.parse.urlencode({"q": strip_search_operators(query), "limit": max_results})

        agent_url = f"https://agentskill.sh/api/agent/search?{params}"
        try:
            data = await asyncio.to_thread(http_get_json, agent_url, timeout=timeout)
            for item in data.get("results", []):
                slug = item.get("slug") or item.get("name")
                if not slug:
                    continue
                candidate = Candidate(
                    name=item.get("name") or slug,
                    kind="Agent Skill",
                    source="agentskill",
                    url=f"https://agentskill.sh/@{slug}",
                    description=item.get("description") or "",
                    stars=item.get("githubStars"),
                    downloads=item.get("installCount"),
                    rating=item.get("score"),
                    updated_at=item.get("updatedAt"),
                    raw={
                        "owner": item.get("owner"),
                        "platforms": item.get("platforms"),
                        "skillTypes": item.get("skillTypes"),
                        "securityScore": item.get("securityScore"),
                        "contentQualityScore": item.get("contentQualityScore"),
                    },
                )
                candidates.setdefault(f"agentskill:{slug}".lower(), candidate)
        except Exception:
            pass

        open_url = (
            "https://www.openagentskill.com/api/agent/skills?"
            + urllib.parse.urlencode(
                {"q": strip_search_operators(query), "limit": max_results, "format": "json"}
            )
        )
        try:
            data = await asyncio.to_thread(http_get_json, open_url, timeout=timeout)
            for item in data.get("skills", []):
                slug = item.get("slug") or item.get("name")
                if not slug:
                    continue
                stats = item.get("stats") or {}
                quality = item.get("quality") or {}
                repo = item.get("repository") or item.get("repo") or ""
                candidate = Candidate(
                    name=item.get("name") or slug,
                    kind="Agent Skill",
                    source="agentskill",
                    url=repo or item.get("url") or f"https://www.openagentskill.com/skills/{slug}",
                    description=item.get("description") or quality.get("summary") or "",
                    evidence=" ".join(item.get("tags") or []),
                    stars=stats.get("stars"),
                    downloads=stats.get("downloads"),
                    rating=stats.get("rating"),
                    updated_at=item.get("updated_at") or item.get("updatedAt"),
                    raw={
                        "category": item.get("category"),
                        "platforms": item.get("platforms"),
                        "verified": item.get("verified"),
                        "quality": quality,
                    },
                )
                candidates.setdefault(f"openagentskill:{slug}".lower(), candidate)
        except Exception:
            pass

    return list(candidates.values())


async def search_skillsmp(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    """Search SkillsMP's anonymous JSON API (rate-limited upstream)."""
    candidates: dict[str, Candidate] = {}
    for query in source_queries(plan, 4):
        url = "https://skillsmp.com/api/v1/skills/search?" + urllib.parse.urlencode(
            {"q": strip_search_operators(query), "page": 1, "limit": max_results}
        )
        try:
            data = await asyncio.to_thread(http_get_json, url, timeout=timeout)
            for item in (data.get("data") or {}).get("skills", []):
                name = item.get("name") or item.get("id")
                if not name:
                    continue
                repo = item.get("githubUrl") or item.get("skillUrl") or ""
                candidate = Candidate(
                    name=name,
                    kind="Agent Skill",
                    source="skillsmp",
                    url=repo,
                    description=item.get("description") or "",
                    stars=item.get("stars"),
                    updated_at=str(item.get("updatedAt") or ""),
                    raw={"author": item.get("author"), "id": item.get("id")},
                )
                candidates.setdefault(f"skillsmp:{item.get('id') or repo or name}".lower(), candidate)
        except Exception:
            continue
    return list(candidates.values())


async def search_clawhub(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    """Search ClawHub's public community skill index."""
    candidates: dict[str, Candidate] = {}
    for query in source_queries(plan, 4):
        url = "https://clawhub.ai/api/v1/search?" + urllib.parse.urlencode(
            {"q": strip_search_operators(query), "limit": max_results}
        )
        try:
            data = await asyncio.to_thread(http_get_json, url, timeout=timeout)
            for item in data.get("results", []):
                name = item.get("displayName") or item.get("name") or item.get("slug")
                if not name:
                    continue
                links = item.get("links") or {}
                canonical = (
                    item.get("canonicalUrl")
                    or links.get("homepage")
                    or links.get("source")
                    or ""
                )
                url_value = ("https://clawhub.ai" + canonical) if canonical.startswith("/") else (canonical or "https://clawhub.ai")
                metrics = item.get("metrics") or {}
                downloads = item.get("downloads") or metrics.get("downloads") or metrics.get("rolling60DayInstalls") or metrics.get("installs")
                candidate = Candidate(
                    name=name,
                    kind="Agent Skill",
                    source="clawhub",
                    url=url_value,
                    description=item.get("summary") or item.get("description") or "",
                    downloads=downloads,
                    stars=item.get("stars"),
                    raw={
                        "trust": item.get("trust"),
                        "official": item.get("official"),
                        "install": item.get("install"),
                    },
                )
                candidates.setdefault(f"clawhub:{item.get('slug') or url_value or name}".lower(), candidate)
        except Exception:
            continue
    return list(candidates.values())


async def search_skillssh(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    """Search skills.sh API when authorized, with a conservative HTML fallback."""
    candidates: dict[str, Candidate] = {}
    for query in source_queries(plan, 3):
        q = strip_search_operators(query)
        api = "https://skills.sh/api/search?" + urllib.parse.urlencode(
            {"q": q, "limit": max_results}
        )
        try:
            data = await asyncio.to_thread(http_get_json, api, timeout=timeout)
            items = data.get("skills") or data.get("results") or []
        except Exception:
            items = []
            try:
                search_url = "https://www.skills.sh/search?" + urllib.parse.urlencode({"q": q})
                html = await asyncio.to_thread(http_get_text, search_url, timeout=timeout)
                links = re.findall(
                    r"https://www\.skills\.sh/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
                    html,
                )
                items = [
                    {"slug": link, "name": link.rsplit("/", 1)[-1], "url": "https://www.skills.sh/" + link}
                    for link in unique_keep_order(links, max_results)
                ]
            except Exception:
                pass
        for item in items[:max_results]:
            name = item.get("name") or item.get("slug")
            if not name:
                continue
            url_value = item.get("url") or item.get("skillUrl") or (
                "https://www.skills.sh/" + item["slug"] if item.get("slug") else "https://www.skills.sh"
            )
            candidate = Candidate(
                name=name,
                kind="Agent Skill",
                source="skillssh",
                url=url_value,
                description=item.get("description") or item.get("summary") or "",
                stars=item.get("stars"),
                downloads=item.get("installs") or item.get("installCount"),
                raw={"slug": item.get("slug")},
            )
            candidates.setdefault(f"skillssh:{url_value}".lower(), candidate)
    return list(candidates.values())


async def search_vscode_marketplace(
    plan: QueryPlan, max_results: int, timeout: float
) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}
    url = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery?api-version=7.2-preview.1"
    headers = {"Accept": "application/json;api-version=7.2-preview.1"}

    for query in source_queries(plan, 4):
        payload = {
            "filters": [
                {
                    "criteria": [{"filterType": 10, "value": strip_search_operators(query)}],
                    "pageNumber": 1,
                    "pageSize": min(max_results, 10),
                    "sortBy": 0,
                    "sortOrder": 0,
                }
            ],
            "flags": 914,
        }
        try:
            data = await asyncio.to_thread(http_post_json, url, payload, headers=headers, timeout=timeout)
        except Exception:
            continue
        for result in data.get("results", []):
            for ext in result.get("extensions", []):
                publisher = ext.get("publisher") or {}
                publisher_name = publisher.get("publisherName") or publisher.get("displayName") or ""
                ext_name = ext.get("extensionName") or ""
                if not publisher_name or not ext_name:
                    continue
                full_id = f"{publisher_name}.{ext_name}"
                stats = {stat.get("statisticName"): stat.get("value") for stat in ext.get("statistics", [])}
                candidate = Candidate(
                    name=ext.get("displayName") or full_id,
                    kind="VS Code extension",
                    source="vscode",
                    url=f"https://marketplace.visualstudio.com/items?itemName={full_id}",
                    description=ext.get("shortDescription") or "",
                    downloads=int(stats.get("install") or stats.get("downloadCount") or 0) or None,
                    rating=float(stats.get("averagerating") or 0) or None,
                    updated_at=ext.get("lastUpdated"),
                    raw={"publisher": publisher_name, "extensionName": ext_name},
                )
                candidates.setdefault(f"vscode:{full_id}".lower(), candidate)
    return list(candidates.values())


async def search_openvsx(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}
    for query in source_queries(plan, 5):
        params = urllib.parse.urlencode({"query": strip_search_operators(query), "size": max_results})
        url = f"https://open-vsx.org/api/-/search?{params}"
        data = await asyncio.to_thread(http_get_json, url, timeout=timeout)
        for ext in data.get("extensions", []):
            namespace = ext.get("namespace") or ""
            name = ext.get("name") or ""
            if not namespace or not name:
                continue
            full_id = f"{namespace}.{name}"
            candidate = Candidate(
                name=ext.get("displayName") or full_id,
                kind="Open VSX extension",
                source="openvsx",
                url=f"https://open-vsx.org/extension/{namespace}/{name}",
                description=ext.get("description") or "",
                downloads=ext.get("downloadCount"),
                rating=ext.get("averageRating"),
                updated_at=ext.get("timestamp"),
                raw={"verified": ext.get("verified"), "version": ext.get("version")},
            )
            candidates.setdefault(f"openvsx:{full_id}".lower(), candidate)
    return list(candidates.values())


async def search_smithery(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    api_key = os.getenv("SMITHERY_API_KEY")
    if not api_key:
        return []

    candidates: dict[str, Candidate] = {}
    headers = {"Authorization": f"Bearer {api_key}"}
    for query in source_queries(plan, 4):
        params = urllib.parse.urlencode({"q": strip_search_operators(query), "pageSize": max_results})
        url = f"https://api.smithery.ai/servers?{params}"
        data = await asyncio.to_thread(http_get_json, url, headers=headers, timeout=timeout)
        items = data.get("servers") or data.get("items") or data.get("results") or []
        for item in items:
            name = item.get("displayName") or item.get("name") or item.get("qualifiedName")
            if not name:
                continue
            candidate = Candidate(
                name=name,
                kind="MCP server",
                source="smithery",
                url=item.get("homepage") or item.get("repository") or item.get("url") or "",
                description=item.get("description") or "",
                downloads=item.get("useCount"),
                rating=item.get("score"),
                updated_at=item.get("updatedAt"),
                raw={
                    "verified": item.get("verified"),
                    "remote": item.get("remote"),
                    "deployed": item.get("deployed"),
                },
            )
            key = (candidate.url or f"smithery:{name}").lower()
            candidates.setdefault(key, candidate)
    return list(candidates.values())


async def search_pulsemcp(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    api_key = os.getenv("PULSEMCP_API_KEY")
    if not api_key:
        return []

    candidates: dict[str, Candidate] = {}
    headers = {"Authorization": f"Bearer {api_key}"}
    for query in source_queries(plan, 4):
        params = urllib.parse.urlencode({"search": strip_search_operators(query), "limit": max_results})
        url = f"https://www.pulsemcp.com/api/v0.1/servers?{params}"
        data = await asyncio.to_thread(http_get_json, url, headers=headers, timeout=timeout)
        for item in data.get("servers", []):
            name = item.get("name") or item.get("slug")
            if not name:
                continue
            candidate = Candidate(
                name=name,
                kind="MCP server",
                source="pulsemcp",
                url=item.get("repository_url") or item.get("url") or "",
                description=item.get("description") or "",
                stars=item.get("stars"),
                updated_at=item.get("updated_at") or item.get("last_seen_at"),
                raw=item,
            )
            key = (candidate.url or f"pulsemcp:{name}").lower()
            candidates.setdefault(key, candidate)
    return list(candidates.values())


async def search_web(plan: QueryPlan, max_results: int, timeout: float) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}
    brave_key = os.getenv("BRAVE_API_KEY")
    web_queries = unique_keep_order(plan.native_audit_queries + source_queries(plan, 4), 6)

    if brave_key:
        headers = {"X-Subscription-Token": brave_key}
        for query in web_queries:
            params = urllib.parse.urlencode({"q": query, "count": min(max_results, 10)})
            url = f"https://api.search.brave.com/res/v1/web/search?{params}"
            data = await asyncio.to_thread(http_get_json, url, headers=headers, timeout=timeout)
            for item in (data.get("web") or {}).get("results", []):
                candidate_url = item.get("url") or ""
                if not candidate_url:
                    continue
                candidate = Candidate(
                    name=item.get("title") or candidate_url,
                    kind="web result",
                    source="web",
                    url=candidate_url,
                    description=item.get("description") or "",
                )
                candidates.setdefault(candidate_url.lower(), candidate)

    # Jina search is best effort. It occasionally rejects or times out; that should not fail the run.
    if not candidates:
        for query in web_queries[:2]:
            params = urllib.parse.urlencode({"q": query})
            url = f"https://s.jina.ai/?{params}"
            try:
                text = await asyncio.to_thread(http_get_text, url, timeout=timeout)
            except Exception:
                continue
            for title, result_url, snippet in parse_jina_results(text)[:max_results]:
                candidate = Candidate(
                    name=title or result_url,
                    kind="web result",
                    source="web",
                    url=result_url,
                    description=snippet,
                )
                candidates.setdefault(result_url.lower(), candidate)

    return list(candidates.values())


def parse_jina_results(text: str) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []
    current_title = ""
    current_url = ""
    current_snippet: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        title_match = re.match(r"^\[(?:\d+)\]\s*(.+)$", line)
        if title_match:
            if current_url:
                results.append((current_title, current_url, " ".join(current_snippet)))
            current_title = title_match.group(1)
            current_url = ""
            current_snippet = []
            continue
        url_match = re.search(r"https?://\S+", line)
        if url_match and not current_url:
            current_url = url_match.group(0).rstrip(")")
            continue
        if current_title and line:
            current_snippet.append(line)
    if current_url:
        results.append((current_title, current_url, " ".join(current_snippet)))
    return results


def canonical_key(candidate: Candidate) -> str:
    url = candidate.url.lower().strip().removeprefix("git+").rstrip("/")
    url = re.sub(r"\.git($|[?#])", r"\1", url)
    github_match = re.match(r"https://github\.com/([^/]+/[^/#?]+)", url)
    if github_match:
        return f"github:{github_match.group(1).lower()}"
    npm_match = re.search(r"npmjs\.com/package/([^/?#]+)", url)
    if npm_match:
        return f"npm:{urllib.parse.unquote(npm_match.group(1)).lower()}"
    if url:
        return url
    return normalize_text(candidate.name)


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for candidate in candidates:
        key = canonical_key(candidate)
        if key not in merged:
            merged[key] = candidate
            continue
        existing = merged[key]
        existing.sources.update(candidate.sources)
        if len(candidate.description) > len(existing.description):
            existing.description = candidate.description
        if len(candidate.evidence) > len(existing.evidence):
            existing.evidence = candidate.evidence
        existing.stars = max_optional(existing.stars, candidate.stars)
        existing.forks = max_optional(existing.forks, candidate.forks)
        existing.downloads = max_optional(existing.downloads, candidate.downloads)
        existing.rating = max_optional(existing.rating, candidate.rating)
        existing.updated_at = max_date_text(existing.updated_at, candidate.updated_at)
        existing.license = existing.license or candidate.license
        existing.archived = existing.archived and candidate.archived
        existing.raw.setdefault("merged_from", []).append(candidate.source)
    return list(merged.values())


def max_optional(a: Any, b: Any) -> Any:
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def max_date_text(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    return max(a, b)


def apply_gates_and_scores(candidate: Candidate, need: NeedProfile) -> None:
    candidate.v0 = bool(candidate.url or candidate.name) and not candidate.archived
    if not candidate.v0:
        candidate.v1 = False
        candidate.rejected_reason = "V0 failed: missing URL/name or archived."
        return

    text = candidate.search_text
    for pattern in need.negative_patterns:
        if pattern in text:
            candidate.v1 = False
            candidate.rejected_reason = f"V1 failed: likely wrong direction ({pattern})."
            return

    missing_groups = [
        group for group in need.required_groups if not any(term in text for term in group)
    ]
    if missing_groups:
        candidate.v1 = False
        candidate.rejected_reason = (
            "V1 failed: missing required concept group "
            + ", ".join("/".join(group) for group in missing_groups)
            + "."
        )
        return

    hard_terms = {term for term in need.hard_terms if len(term.split()) == 1}
    hard_hits = {term for term in hard_terms if term in text}
    positive_terms = {term for term in need.positive_terms if len(term.split()) == 1}
    positive_hits = {term for term in positive_terms if term in text}

    phrase_terms = {term for term in need.positive_terms if len(term.split()) > 1}
    phrase_hits = {term for term in phrase_terms if term in text}

    hard_required = max(1, math.ceil(len(hard_terms) * 0.5)) if hard_terms else 0
    hard_ok = len(hard_hits) >= hard_required
    positive_ok = len(positive_hits) >= max(2, math.ceil(len(positive_terms) * 0.25)) if positive_terms else True
    phrase_bonus_ok = bool(phrase_hits)

    candidate.v1 = hard_ok and (positive_ok or phrase_bonus_ok)
    if not candidate.v1:
        candidate.rejected_reason = (
            "V1 failed: source metadata does not provide enough direct evidence for the need."
        )
        return

    candidate.goal_match = score_goal_match(candidate, need, hard_hits, positive_hits, phrase_hits)
    candidate.evidence_strength = score_evidence_strength(candidate, hard_hits, phrase_hits)
    candidate.project_quality = score_project_quality(candidate)
    candidate.landing_friction = score_landing_friction(candidate)
    candidate.multi_source = min(1.0, (len(candidate.sources) - 1) / 3)
    candidate.score = (
        0.45 * candidate.goal_match
        + 0.20 * candidate.evidence_strength
        + 0.20 * candidate.project_quality
        + 0.10 * candidate.landing_friction
        + 0.05 * candidate.multi_source
    )
    candidate.reasons = build_reasons(candidate)


def score_goal_match(
    candidate: Candidate,
    need: NeedProfile,
    hard_hits: set[str],
    positive_hits: set[str],
    phrase_hits: set[str],
) -> float:
    hard_denominator = max(1, len({term for term in need.hard_terms if len(term.split()) == 1}))
    positive_denominator = max(1, len({term for term in need.positive_terms if len(term.split()) == 1}))
    hard_score = len(hard_hits) / hard_denominator
    positive_score = len(positive_hits) / positive_denominator
    phrase_score = min(1.0, len(phrase_hits) * 0.35)
    direct_name_bonus = 0.15 if any(term in normalize_text(candidate.name) for term in hard_hits) else 0
    return min(1.0, 0.55 * hard_score + 0.30 * positive_score + phrase_score + direct_name_bonus)


def score_evidence_strength(candidate: Candidate, hard_hits: set[str], phrase_hits: set[str]) -> float:
    score = 0.25
    if candidate.description:
        score += 0.20
    if candidate.evidence:
        score += 0.20
    if hard_hits:
        score += min(0.20, 0.05 * len(hard_hits))
    if phrase_hits:
        score += min(0.15, 0.08 * len(phrase_hits))
    return min(1.0, score)


def score_project_quality(candidate: Candidate) -> float:
    if candidate.archived:
        return 0.0
    score = 0.20
    if candidate.stars:
        score += min(0.25, math.log10(candidate.stars + 1) / 16)
    if candidate.downloads:
        score += min(0.25, math.log10(candidate.downloads + 1) / 18)
    if candidate.rating:
        score += min(0.10, float(candidate.rating) / 50)
    days = age_days(candidate.updated_at)
    if days is not None:
        if days <= 30:
            score += 0.20
        elif days <= 180:
            score += 0.14
        elif days <= 365:
            score += 0.08
    if candidate.license:
        score += 0.10
    if candidate.description:
        score += 0.05
    return min(1.0, score)


def score_landing_friction(candidate: Candidate) -> float:
    text = candidate.search_text
    score = 0.65
    if candidate.license and candidate.license.lower() not in {"unknown", "other"}:
        score += 0.15
    if any(source in candidate.sources for source in {"github", "npm", "openvsx", "vscode"}):
        score += 0.10
    if "api key" in text or "secret" in text or "token" in text:
        score -= 0.15
    if "docker" in text or "npx" in text or "npm" in text or "pip" in text:
        score += 0.05
    if "paid" in text or "pricing" in text or "enterprise" in text:
        score -= 0.10
    return max(0.0, min(1.0, score))


def build_reasons(candidate: Candidate) -> list[str]:
    reasons: list[str] = []
    if candidate.goal_match >= 0.8:
        reasons.append("directly matches the hard terms and direction")
    elif candidate.goal_match >= 0.55:
        reasons.append("matches several important terms")
    if candidate.evidence:
        reasons.append("has README/tool-schema/keyword evidence")
    elif candidate.description:
        reasons.append("has description-level evidence")
    if candidate.stars:
        reasons.append(f"{candidate.stars} GitHub stars")
    if candidate.downloads:
        reasons.append(f"{candidate.downloads} downloads/uses")
    days = age_days(candidate.updated_at)
    if days is not None:
        if days <= 30:
            reasons.append("updated within 30 days")
        elif days <= 180:
            reasons.append("updated within 6 months")
    if len(candidate.sources) > 1:
        reasons.append(f"found in {len(candidate.sources)} sources")
    return reasons[:5]


def age_days(date_text: str | None) -> int | None:
    if not date_text:
        return None
    raw = date_text.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = dt.datetime.strptime(date_text[:10], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    return max(0, (now - parsed).days)


async def run_search(plan: QueryPlan, sources: list[str], max_per_source: int, timeout: float) -> list[Candidate]:
    tasks = []
    if "github" in sources:
        tasks.append(safe_call("github", search_github(plan, max_per_source, timeout)))
    if "npm" in sources:
        tasks.append(safe_call("npm", search_npm(plan, max_per_source, timeout)))
    if "mcp" in sources:
        tasks.append(safe_call("mcp", search_official_mcp(plan, max_per_source, timeout)))
    if "glama" in sources:
        tasks.append(safe_call("glama", search_glama(plan, max_per_source, timeout)))
    if "agentskill" in sources:
        tasks.append(safe_call("agentskill", search_agentskill(plan, max_per_source, timeout)))
    if "skillsmp" in sources:
        tasks.append(safe_call("skillsmp", search_skillsmp(plan, max_per_source, timeout)))
    if "clawhub" in sources:
        tasks.append(safe_call("clawhub", search_clawhub(plan, max_per_source, timeout)))
    if "skillssh" in sources:
        tasks.append(safe_call("skillssh", search_skillssh(plan, max_per_source, timeout)))
    if "vscode" in sources:
        tasks.append(safe_call("vscode", search_vscode_marketplace(plan, max_per_source, timeout)))
    if "openvsx" in sources:
        tasks.append(safe_call("openvsx", search_openvsx(plan, max_per_source, timeout)))
    if "web" in sources:
        tasks.append(safe_call("web", search_web(plan, max_per_source, timeout)))
    if "smithery" in sources:
        tasks.append(safe_call("smithery", search_smithery(plan, max_per_source, timeout)))
    if "pulsemcp" in sources:
        tasks.append(safe_call("pulsemcp", search_pulsemcp(plan, max_per_source, timeout)))

    results = await asyncio.gather(*tasks)
    candidates = [candidate for group in results for candidate in group]
    deduped = dedupe_candidates(candidates)
    for candidate in deduped:
        apply_gates_and_scores(candidate, plan.profile)
    return sorted(deduped, key=lambda c: c.score, reverse=True)


def candidate_to_dict(candidate: Candidate) -> dict[str, Any]:
    return {
        "name": candidate.name,
        "kind": candidate.kind,
        "sources": sorted(candidate.sources),
        "url": candidate.url,
        "description": candidate.description,
        "evidence": compact(candidate.evidence, 700),
        "stars": candidate.stars,
        "downloads": candidate.downloads,
        "updated_at": candidate.updated_at,
        "license": candidate.license,
        "v0": candidate.v0,
        "v1": candidate.v1,
        "rejected_reason": candidate.rejected_reason,
        "score": round(candidate.score, 4),
        "scores": {
            "goal_match": round(candidate.goal_match, 4),
            "evidence_strength": round(candidate.evidence_strength, 4),
            "project_quality": round(candidate.project_quality, 4),
            "landing_friction": round(candidate.landing_friction, 4),
            "multi_source": round(candidate.multi_source, 4),
        },
        "reasons": candidate.reasons,
    }


def print_text_report(plan: QueryPlan, candidates: list[Candidate], limit: int, include_rejected: bool) -> None:
    passed = [candidate for candidate in candidates if candidate.v0 and candidate.v1]
    rejected = [candidate for candidate in candidates if not (candidate.v0 and candidate.v1)]

    print("# Tool Scout Report")
    print()
    print(f"Need: {plan.raw}")
    print()
    if plan.native_audit_queries:
        print("Native feature audit:")
        print("- Before ranking external tools, check whether the target product already solves this.")
        print("- Inspect: " + "; ".join(NATIVE_FEATURE_CHECKLIST) + ".")
        print("- Suggested official/native queries:")
        for query in plan.native_audit_queries:
            print(f"  - {query}")
        print()
    print("Query plan:")
    for query in plan.queries:
        print(f"- {query}")
    print()
    print(f"Credible candidates: {len(passed)}")
    print()

    if not passed:
        print("No candidates passed V0/V1. Try a broader wording or enable additional API keys.")
    for index, candidate in enumerate(passed[:limit], start=1):
        print(f"{index}. {candidate.name} ({candidate.kind})")
        print(f"   URL: {candidate.url}")
        print(f"   Sources: {', '.join(sorted(candidate.sources))}")
        print(f"   Score: {candidate.score:.2f}")
        if candidate.description:
            print(f"   Evidence: {compact(candidate.description, 220)}")
        elif candidate.evidence:
            print(f"   Evidence: {compact(candidate.evidence, 220)}")
        if candidate.reasons:
            print(f"   Why: {'; '.join(candidate.reasons)}")
        facts = []
        if candidate.stars is not None:
            facts.append(f"stars={candidate.stars}")
        if candidate.downloads is not None:
            facts.append(f"downloads={candidate.downloads}")
        if candidate.updated_at:
            facts.append(f"updated={candidate.updated_at[:10]}")
        if candidate.license:
            facts.append(f"license={candidate.license}")
        if facts:
            print(f"   Signals: {', '.join(facts)}")
        print()

    if include_rejected and rejected:
        print("Rejected or lower-confidence results:")
        for candidate in rejected[:limit]:
            print(f"- {candidate.name} ({candidate.kind}): {candidate.rejected_reason}")


def parse_sources(raw: str) -> list[str]:
    if raw == "all":
        return list(DEFAULT_SOURCES)
    aliases = {"skills.sh": "skillssh", "skillsmp.com": "skillsmp", "clawhub.ai": "clawhub"}
    sources = [aliases.get(source.strip().lower(), source.strip().lower()) for source in raw.split(",") if source.strip()]
    unknown = [source for source in sources if source not in DEFAULT_SOURCES]
    if unknown:
        raise SystemExit(f"Unknown sources: {', '.join(unknown)}")
    return sources


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find existing tools for a software-tool need.")
    parser.add_argument("need", help="Software-tool need, for example: Feishu bot controls Claude Code")
    parser.add_argument("--limit", type=int, default=10, help="Number of ranked results to print")
    parser.add_argument(
        "--sources",
        default="all",
        help="Comma-separated sources: github,npm,mcp,glama,agentskill,skillsmp,clawhub,skillssh,vscode,openvsx,web,smithery,pulsemcp",
    )
    parser.add_argument("--max-per-source", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text report")
    parser.add_argument("--include-rejected", action="store_true")
    return parser.parse_args(argv)


async def async_main(argv: list[str]) -> int:
    args = parse_args(argv)
    sources = parse_sources(args.sources)
    plan = build_query_plan(args.need)
    candidates = await run_search(plan, sources, args.max_per_source, args.timeout)

    if args.json:
        payload = {
            "need": args.need,
            "native_feature_audit": {
                "required": bool(plan.native_audit_queries),
                "checklist": list(NATIVE_FEATURE_CHECKLIST),
                "queries": plan.native_audit_queries,
            },
            "queries": plan.queries,
            "sources": sources,
            "candidates": [
                candidate_to_dict(candidate)
                for candidate in candidates
                if args.include_rejected or (candidate.v0 and candidate.v1)
            ][: args.limit],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text_report(plan, candidates, args.limit, args.include_rejected)
    return 0


def main() -> int:
    try:
        return asyncio.run(async_main(sys.argv[1:]))
    except KeyboardInterrupt:
        return 130
    except urllib.error.HTTPError as exc:
        print(f"HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
