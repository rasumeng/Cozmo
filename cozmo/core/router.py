import json
import logging
import re
import urllib.request

from .llm import StatelessLLM

log = logging.getLogger("cozmo.router")


class ToolRouter:
    CATEGORIES = {
        "git_status": {
            "domain": "git", "priority": 100,
            "keywords": ["status", "current state"],
            "tools": ["git_git_status"],
        },
        "git_diff": {
            "domain": "git", "priority": 90,
            "keywords": ["diff", "show diff", "view diff", "see diff", "show changes", "view changes", "unstaged", "staged"],
            "tools": ["git_git_diff", "git_git_diff_unstaged", "git_git_diff_staged"],
        },
        "git_commit": {
            "domain": "git", "priority": 80,
            "keywords": ["commit this", "commit changes", "commit the", "stage", "git add"],
            "tools": ["git_git_add", "git_git_commit"],
        },
        "git_log": {
            "domain": "git", "priority": 70,
            "keywords": ["log", "history", "recent commits"],
            "tools": ["git_git_log", "git_git_show"],
        },
        "git_branch": {
            "domain": "git", "priority": 60,
            "keywords": ["branch", "branches", "checkout", "switch", "create branch"],
            "tools": ["git_git_branch", "git_git_create_branch", "git_git_checkout"],
        },
        "git_full": {
            "domain": "git", "priority": 50,
            "keywords": ["reset", "revert"],
            "tools": ["git_git_reset"],
        },
        "git_ambiguous": {
            "domain": "git", "priority": 10,
            "keywords": ["git", "repository", "repo", "version control"],
            "tools": ["git_git_status", "git_git_log", "git_git_diff", "git_git_commit", "git_git_add", "git_git_branch"],
        },
        "filesystem": {
            "keywords": ["read file", "open file", "write file", "read", "write", "directory", "folder", "delete", "move", "copy", "mkdir", "list", "search files", "tree", "edit", "create", "rename", "open", "save", "path"],
            "tools": ["filesystem_read_file", "filesystem_read_text_file", "filesystem_read_media_file", "filesystem_read_multiple_files", "filesystem_write_file", "filesystem_edit_file", "filesystem_create_directory", "filesystem_list_directory", "filesystem_list_directory_with_sizes", "filesystem_directory_tree", "filesystem_move_file", "filesystem_search_files", "filesystem_get_file_info", "filesystem_list_allowed_directories"],
        },
        "web": {
            "keywords": ["web search", "search online", "search the web", "look up online", "find", "lookup", "url", "fetch", "scrape", "browse", "http", "website", "web", "google", "online", "internet"],
            "tools": ["web_search", "web_search_pipeline", "fetch_url", "web_fetch"],
        },
        "code": {
            "keywords": ["run", "execute", "python", "bash", "shell", "compile", "test", "pip", "install", "script", "code", "calculator", "program"],
            "tools": ["execute_python", "run_command", "calculator"],
        },
        "knowledge": {
            "keywords": ["knowledge", "notes", "reference", "document", "learn", "remember", "save to knowledge", "okf", "note", "journal"],
            "tools": ["read_knowledge", "write_knowledge"],
        },
    }

    def __init__(self, use_llm: bool = True, llm_model: str = "qwen3:1.7b", base_url: str = "http://localhost:11434"):
        self.use_llm = use_llm
        self.classifier = StatelessLLM(llm_model, base_url) if use_llm else None

    def _keyword_match(self, query: str) -> list[dict]:
        query_lower = query.lower()
        matches = []
        for cat_name, cat_data in self.CATEGORIES.items():
            for keyword in cat_data.get("keywords", []):
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, query_lower):
                    matches.append({
                        "category": cat_name,
                        "domain": cat_data.get("domain"),
                        "priority": cat_data.get("priority", 0),
                    })
                    break
        return matches

    def _resolve_matches(self, matches: list[dict]) -> list[str]:
        domain_best = {}
        standalone = []
        for m in matches:
            domain = m["domain"]
            if domain:
                if domain not in domain_best or m["priority"] > domain_best[domain]["priority"]:
                    domain_best[domain] = m
            else:
                standalone.append(m["category"])
        return standalone + [m["category"] for m in domain_best.values()]

    def _llm_classify(self, query: str) -> list[str]:
        if not self.classifier:
            return []
        category_labels = {
            "git_ambiguous": "git/version control",
            "filesystem": "file operations",
            "web": "web search/fetch",
            "code": "code execution",
            "knowledge": "knowledge base",
        }
        cat_list = ", ".join(f'"{k}" ({v})' for k, v in category_labels.items())
        prompt = f"Categories: {cat_list}\n\nQuery: {query}\n\nCategories:"
        system = "Classify queries into tool categories. Reply with ONLY a JSON array."
        try:
            raw = self.classifier.generate(prompt, system_prompt=system, structured=True)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                categories = json.loads(raw[start:end])
                return [c for c in categories if c in self.CATEGORIES]
        except Exception as e:
            log.warning("classification failed: %s", e)
        return []

    def classify(self, query: str) -> list[str] | None:
        if not query or not query.strip():
            return None
        raw_matches = self._keyword_match(query)
        if raw_matches:
            return self._resolve_matches(raw_matches)
        if self.use_llm:
            matches = self._llm_classify(query[:1000])
            if matches:
                return matches
        return None

    # Read-only / chat-safe tools offered when classification fails.
    # No code-execution or file-write tools here.
    SAFE_FALLBACK_TOOLS = {
        "web_search", "web_search_pipeline", "fetch_url", "web_fetch",
        "read_knowledge",
        "filesystem_read_file", "filesystem_read_text_file",
        "filesystem_list_directory", "filesystem_get_file_info",
    }

    def _safe_fallback(self, all_tools: list) -> list:
        log.warning("no category match; falling back to safe read-only tool set")
        return [t for t in all_tools if t.__name__ in self.SAFE_FALLBACK_TOOLS]

    def get_tools(self, query: str, all_tools: list) -> list:
        categories = self.classify(query)
        if categories is None:
            return self._safe_fallback(all_tools)
        tool_names = set()
        for cat_name in categories:
            cat_tools = self.CATEGORIES[cat_name].get("tools", [])
            tool_names.update(cat_tools)
        filtered = [t for t in all_tools if t.__name__ in tool_names]
        if not filtered:
            return self._safe_fallback(all_tools)
        print(f"[router] Categories: {categories} -> {len(filtered)} tools")
        return filtered
