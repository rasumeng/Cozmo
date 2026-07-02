"""Agent registry — manages primary agents, Plan vs Build, custom markdown agents."""

from pathlib import Path


def _parse_markdown_agent(path: Path) -> dict | None:
    """Parse YAML frontmatter from a markdown agent file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    front = text[3:end].strip()
    body = text[end + 3:].strip()
    meta = {"prompt": body}
    for line in front.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip("\"'")
    return meta


class AgentRegistry:
    """Holds agent instances. Cycle via switch()."""

    def __init__(self, project_path: Path, cfg: dict, auto: bool = False):
        self.auto = auto
        self.project_path = project_path
        self.cfg = cfg
        self._agents: list = []
        self._names: list[str] = []
        self._current = 0
        self._build()

    def _build(self):
        agent_cfg = self.cfg.get("agents", {})
        primary_names = agent_cfg.get("primary", ["build", "plan"])

        for name in primary_names:
            agent = self._create(name)
            self._agents.append(agent)
            self._names.append(name)

        self._load_custom()

    def _create(self, name: str):
        agent_cfg = self.cfg.get("agents", {}).get(name, {})
        default_model = self.cfg.get("models", {}).get("coder", "qwen3:8b")
        model = agent_cfg.get("model", default_model)

        if name == "plan":
            from .plan_agent import PlanAgent
            return PlanAgent(model, self.project_path, self.cfg, agent_cfg, auto=self.auto)
        from .code_agent import CodeAgent
        return CodeAgent(model, self.project_path, self.cfg, agent_cfg, auto=self.auto)

    def _load_custom(self):
        agents_dir = self.project_path / ".cozmo" / "agents"
        if not agents_dir.is_dir():
            return
        for f in sorted(agents_dir.glob("*.md")):
            meta = _parse_markdown_agent(f)
            if meta is None:
                continue
            name = meta.get("name") or f.stem
            if name in self._names:
                continue
            model = meta.get("model", self.cfg.get("models", {}).get("coder", "qwen3:8b"))
            from .code_agent import CodeAgent
            agent = CodeAgent(model, self.project_path, self.cfg, {"prompt": meta.get("prompt", ""), "auto": self.auto})
            self._agents.append(agent)
            self._names.append(name)

    def switch(self, direction: int = 1):
        if len(self._agents) < 2:
            return
        self._current = (self._current + direction) % len(self._agents)

    @property
    def current(self):
        return self._agents[self._current]

    @property
    def current_name(self) -> str:
        return self._names[self._current]

    def list(self) -> list[tuple[str, int]]:
        return [(n, i) for i, n in enumerate(self._names)]
