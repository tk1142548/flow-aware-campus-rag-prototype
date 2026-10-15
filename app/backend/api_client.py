"""Unified client for the generation, embedding and rerank endpoints.

All three capabilities sit behind one object so that experiments can record
calls, tokens and cost in a single place, and so that every request is cached
on disk. The cache matters for more than speed: a rerun must not silently
change results because a remote model drifted.

Nothing here is allowed to know about evaluation labels. It receives plain
text and returns plain text or scores.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import httpx

COMPATIBLE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
RERANK_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
EMBED_BATCH = 10

DEFAULT_CHAT_MODEL = "qwen-plus"
DEFAULT_EMBED_MODEL = "text-embedding-v4"
DEFAULT_RERANK_MODEL = "gte-rerank-v2"

# CNY per 1K tokens. Only used to report an approximate cost.
PRICES = {
    "qwen-plus": {"input": 0.0008, "output": 0.002},
    "qwen-max": {"input": 0.0024, "output": 0.0096},
    "qwen-flash": {"input": 0.00015, "output": 0.0015},
    "text-embedding-v4": {"input": 0.0005, "output": 0.0},
    "gte-rerank-v2": {"input": 0.0008, "output": 0.0},
}


class ApiError(RuntimeError):
    pass


class ApiClient:
    """Chat / embed / rerank with disk cache, retry and cost accounting."""

    def __init__(
        self,
        cache_dir: Path | str,
        api_key: str | None = None,
        base_url: str = COMPATIBLE_BASE,
        chat_model: str = DEFAULT_CHAT_MODEL,
        embed_model: str = DEFAULT_EMBED_MODEL,
        rerank_model: str = DEFAULT_RERANK_MODEL,
        timeout: float = 120.0,
        max_retries: int = 4,
    ) -> None:
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (os.getenv("OPENAI_BASE_URL") or base_url).rstrip("/")
        self.chat_model = os.getenv("OPENAI_MODEL") or chat_model
        self.embed_model = os.getenv("DASHSCOPE_EMBED_MODEL") or embed_model
        self.rerank_model = os.getenv("DASHSCOPE_RERANK_MODEL") or rerank_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.stats: dict[str, Any] = {
            "chat_calls": 0,
            "chat_cache_hits": 0,
            "embed_calls": 0,
            "embed_cache_hits": 0,
            "rerank_calls": 0,
            "rerank_cache_hits": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "embed_tokens": 0,
            "cost_cny": 0.0,
            "json_repairs": 0,
        }

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # ---------------------------------------------------------------- cache

    def _cache_path(self, namespace: str, payload: Any) -> Path:
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:32]
        folder = self.cache_dir / namespace
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{digest}.json"

    def _cache_read(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _cache_write(self, path: Path, value: Any) -> None:
        # Unique per process AND per thread: workers share one cache directory.
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            # A concurrent reader on Windows can briefly hold the target open;
            # failing to cache is harmless, failing the experiment is not.
            tmp.replace(path)
        except OSError:
            tmp.unlink(missing_ok=True)

    def _post(self, url: str, payload: dict, headers: dict) -> dict:
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
                if response.status_code == 429 or response.status_code >= 500:
                    raise ApiError(f"retryable {response.status_code}: {response.text[:200]}")
                if response.status_code >= 400:
                    raise ApiError(f"{response.status_code}: {response.text[:300]}")
                return response.json()
            except (httpx.HTTPError, ApiError) as error:
                last = error
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        raise ApiError(f"request failed after {self.max_retries} attempts: {last}")

    def _headers(self) -> dict:
        if not self.enabled:
            raise ApiError("no API key configured (set DASHSCOPE_API_KEY)")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _bump(self, **deltas: float) -> None:
        with self._lock:
            for key, delta in deltas.items():
                self.stats[key] = self.stats.get(key, 0) + delta

    @staticmethod
    def _cost_of(model: str, prompt: int, completion: int) -> float:
        price = PRICES.get(model)
        if not price:
            return 0.0
        return prompt / 1000 * price["input"] + completion / 1000 * price["output"]

    # ----------------------------------------------------------------- chat

    def chat(
        self,
        messages: Sequence[dict],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        use_cache: bool = True,
    ) -> str:
        """Return the assistant text. Raises ApiError on failure."""
        model = model or self.chat_model
        payload = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        path = self._cache_path("chat", payload)
        if use_cache:
            cached = self._cache_read(path)
            if cached is not None:
                self._bump(chat_cache_hits=1)
                return cached["text"]

        data = self._post(f"{self.base_url}/chat/completions", payload, self._headers())
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        self._bump(chat_calls=1, prompt_tokens=prompt, completion_tokens=completion,
                   cost_cny=self._cost_of(model, prompt, completion))
        if use_cache:
            self._cache_write(path, {"text": text, "model": model, "usage": usage})
        return text

    def chat_json(
        self,
        messages: Sequence[dict],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> Any:
        """Chat and parse a JSON object out of the reply.

        A reply that is not valid JSON as written is repaired by `extract_json`.
        The reply is scored on what it says, not on how it punctuates, so a stray
        aside or a missing closing bracket must not turn a good answer into a
        missing one. A reply that cannot be repaired still raises, as before.
        """
        text = self.chat(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )
        value, repaired = parse_json_reply(text)
        if repaired:
            self._bump(json_repairs=1)
        return value

    # ---------------------------------------------------------------- embed

    def embed(self, texts: Sequence[str], *, model: str | None = None) -> list[list[float]]:
        model = model or self.embed_model
        out: list[list[float]] = []
        pending: list[str] = []
        for text in texts:
            cached = self._cache_read(self._cache_path("embed", {"model": model, "text": text}))
            if cached is not None:
                self._bump(embed_cache_hits=1)
                out.append(cached["vector"])
            else:
                pending.append(text)
                out.append([])

        pending_index = [i for i, vec in enumerate(out) if not vec]
        for start in range(0, len(pending), EMBED_BATCH):
            batch = pending[start : start + EMBED_BATCH]
            data = self._post(
                f"{self.base_url}/embeddings",
                {"model": model, "input": batch, "dimensions": 1024},
                self._headers(),
            )
            rows = sorted(data["data"], key=lambda row: row["index"])
            tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
            self._bump(embed_calls=1, embed_tokens=tokens,
                       cost_cny=self._cost_of(model, tokens, 0))
            for offset, row in enumerate(rows):
                vector = row["embedding"]
                text = batch[offset]
                self._cache_write(
                    self._cache_path("embed", {"model": model, "text": text}),
                    {"vector": vector},
                )
                out[pending_index[start + offset]] = vector
        return out

    # --------------------------------------------------------------- rerank

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int | None = None,
        model: str | None = None,
    ) -> list[tuple[int, float]]:
        """Return (document_index, relevance_score) sorted by relevance."""
        if not documents:
            return []
        model = model or self.rerank_model
        top_n = top_n or len(documents)
        payload = {
            "model": model,
            "input": {"query": query, "documents": list(documents)},
            "parameters": {"return_documents": False, "top_n": top_n},
        }
        path = self._cache_path("rerank", payload)
        cached = self._cache_read(path)
        if cached is not None:
            self._bump(rerank_cache_hits=1)
            return [(row["index"], row["relevance_score"]) for row in cached["results"]]

        data = self._post(RERANK_ENDPOINT, payload, self._headers())
        results = data["output"]["results"]
        tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
        self._bump(rerank_calls=1, cost_cny=self._cost_of(model, tokens, 0))
        self._cache_write(path, {"results": results})
        return [(row["index"], row["relevance_score"]) for row in results]

    # ---------------------------------------------------------------- misc

    def cost_summary(self) -> dict:
        return dict(self.stats)


def extract_json(text: str) -> Any:
    """Pull a JSON value out of a model reply that may be fenced or padded."""
    return parse_json_reply(text)[0]


def parse_json_reply(text: str) -> tuple[Any, bool]:
    """Return the reply's JSON value and whether a repair was needed.

    Three shapes of near-miss are recovered, in order: text that sits outside any
    string and could not be legal JSON, and a reply cut off before its closing
    bracket. Both were observed on real runs and both leave the answer itself
    intact, so scoring must not treat them as a missing answer.
    """
    candidate = _json_candidate(text)
    attempts = [
        candidate,
        strip_text_outside_strings(candidate),
        close_truncated(candidate),
        close_truncated(strip_text_outside_strings(candidate)),
    ]
    for index, attempt in enumerate(attempts):
        try:
            return json.loads(attempt), index > 0
        except json.JSONDecodeError:
            continue
    raise ValueError(f"no parsable JSON object in reply: {text[:200]}")


def _json_candidate(text: str) -> str:
    """Slice out the first complete JSON value, or all of it if it is unfinished.

    The slice stops where bracket depth returns to zero, so a bracket appearing
    inside a string cannot end it early — which is what a plain "last closing
    bracket" rule does when the reply is truncated.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        if stripped.lstrip().lower().startswith("json"):
            stripped = stripped.lstrip()[4:]
    starts = [i for i in (stripped.find("{"), stripped.find("[")) if i != -1]
    if not starts:
        raise ValueError(f"no JSON value in reply: {text[:200]}")
    start = min(starts)
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        character = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "{[":
            depth += 1
        elif character in "}]":
            depth -= 1
            if depth <= 0:
                return stripped[start : index + 1]
    return stripped[start:]


def close_truncated(text: str) -> str:
    """Finish a reply that was cut off: close the open string, then the brackets."""
    out: list[str] = []
    stack: list[str] = []
    in_string = False
    escaped = False
    for character in text:
        out.append(character)
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "{[":
            stack.append("}" if character == "{" else "]")
        elif character in "}]" and stack:
            stack.pop()
    if in_string:
        out.append('"')
    while stack:
        out.append(stack.pop())
    return "".join(out)


_STRUCTURAL = set('{}[]:,"')


def strip_text_outside_strings(text: str) -> str:
    """Drop everything outside a string literal that JSON syntax cannot contain.

    A reply such as ``["所需材料", "办理入口"（因证据中没有相关内容）]`` is one
    stray parenthetical away from being valid; the parenthesis and the aside that
    follows it are not part of any string, so removing them restores the object.
    Characters inside strings are never touched.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            out.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            out.append(character)
        elif character in _STRUCTURAL or character.isascii():
            out.append(character)
    return "".join(out)
