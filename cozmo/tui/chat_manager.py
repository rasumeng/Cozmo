import json
import re
from datetime import datetime
from pathlib import Path

from ..core.llm import OllamaModel

TOPIC_PROMPT = """Generate a short 3-5 word title for this conversation topic.
Respond with ONLY the title, no extra text, no punctuation.

User: {text}
Title:"""


class ChatManager:
    def __init__(
        self,
        storage_dir: str | Path,
        classifier_model: str = "qwen3:0.6b",
        base_url: str = "http://localhost:11434",
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.storage_dir / "index.json"
        self._index = self._load_index()
        self._classifier = OllamaModel(classifier_model, base_url)

    def _load_index(self) -> dict:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text("utf-8"))
        return {"chats": []}

    def _save_index(self):
        self.index_path.write_text(json.dumps(self._index, indent=2, ensure_ascii=False), "utf-8")

    def _generate_title(self, first_message: str) -> str:
        try:
            raw = self._classifier.invoke(TOPIC_PROMPT.format(text=first_message)).strip()
            raw = re.sub(r'[^\w\s-]', '', raw).strip()
            if raw and not raw.lower().startswith("error"):
                return raw[:60]
        except Exception:
            pass
        words = re.findall(r'\w+', first_message)
        return (" ".join(words[:3]).capitalize() or "New Chat")[:60]

    def _slugify(self, title: str) -> str:
        slug = title.lower().replace(" ", "-")
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        return slug[:50]

    def list_chats(self) -> list[dict]:
        return sorted(self._index["chats"], key=lambda c: c["created"], reverse=True)

    def create_chat(self, first_message: str) -> tuple[str, str]:
        title = self._generate_title(first_message)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        chat_id = f"{ts}_{self._slugify(title)}"

        entry = {
            "id": chat_id,
            "title": title,
            "created": datetime.now().isoformat(),
            "msg_count": 0,
        }
        self._index["chats"].insert(0, entry)
        self._save_index()

        md_path = self.storage_dir / f"{chat_id}.md"
        md_path.write_text(f"# {title}\n\n", "utf-8")

        return chat_id, title

    def append(self, chat_id: str, role: str, text: str):
        md_path = self.storage_dir / f"{chat_id}.md"
        role_label = "User" if role == "user" else "Cozmo"
        with md_path.open("a", encoding="utf-8") as f:
            f.write(f"## {role_label}\n{text}\n\n")

        for chat in self._index["chats"]:
            if chat["id"] == chat_id:
                chat["msg_count"] += 1
                break
        self._save_index()

    def load_chat(self, chat_id: str) -> tuple[str, list[dict]]:
        md_path = self.storage_dir / f"{chat_id}.md"
        if not md_path.exists():
            return "Untitled", []

        content = md_path.read_text("utf-8")
        lines = content.split("\n")

        title = "Untitled"
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()

        messages = []
        current_role = None
        current_text = []

        for line in lines[1:]:
            m = re.match(r"^## (User|Cozmo)$", line.strip())
            if m:
                if current_role:
                    messages.append({"role": current_role, "text": "\n".join(current_text).strip()})
                current_role = "user" if m.group(1) == "User" else "assistant"
                current_text = []
            elif current_role:
                current_text.append(line)

        if current_role:
            messages.append({"role": current_role, "text": "\n".join(current_text).strip()})

        return title, messages

    def get_title(self, chat_id: str) -> str:
        for chat in self._index["chats"]:
            if chat["id"] == chat_id:
                return chat["title"]
        for chat in self.list_chats():
            t, _ = self.load_chat(chat["id"])
            return t
        return "Untitled"
