"""Phase II — auto-discovery of recurring prompt intents from conversation logs.

Reads Claude Code project logs (~/.claude/projects/*/*.jsonl), extracts the
user's own prompts, clusters near-duplicate intents, and proposes high-precision
candidate aliases for binary human confirmation (OQ3 = HDBSCAN + binary, locked).

Design notes:
  * Precision over recall. The logs are full of pasted agent output, screenshots,
    and slash-command noise — we filter hard so a suggested alias is almost always
    a real recurring task, accepting that we miss some.
  * Cold-start backend is TF-IDF + HDBSCAN (no torch). sentence-transformers is a
    later semantic upgrade behind the [discovery] extra; the clustering interface
    is identical so swapping it in changes one function.
  * Discovery only proposes. Nothing is signed until a human accepts, at which
    point the normal trust spine (create_alias) mints identity + signs the intent.
"""
from __future__ import annotations

import glob
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Prompts outside this window are almost never reusable aliases: shorter is a
# fragment ("yes", "go on"), longer is usually pasted content or a transcript.
MIN_CHARS = 24
MAX_CHARS = 600
# Lines/blocks that are harness scaffolding, not user intent.
_NOISE_MARKERS = (
    "<command-name>", "<command-message>", "<local-command", "<system-reminder>",
    "<command-args>", "caveat:", "[request interrupted", "tool_use_id",
    "this session is being continued", "<bash-", "stdout",
)
# Pasted terminal sessions ("user@host:~$ …", "PS C:\\…>") are the biggest
# false-positive source — they cluster tightly but are not user intents.
_SHELL_RE = re.compile(r"[\w.-]+@[\w.-]+:~?[\w/.-]*[$#]|PS [A-Z]:\\")
_STOP = {
    "the", "a", "an", "this", "that", "to", "of", "in", "on", "for", "and", "or",
    "is", "it", "i", "you", "me", "my", "we", "please", "can", "could", "would",
    "with", "into", "from", "as", "at", "be", "do", "if", "so", "all", "any",
    "have", "has", "was", "are", "what", "how", "should", "now", "here", "heres",
    "want", "need", "like", "just", "also", "get", "got", "its", "there", "these",
}


@dataclass
class Prompt:
    text: str
    project: str
    ts: str = ""  # ISO timestamp if the log row carried one (for recurrence velocity)


@dataclass
class Candidate:
    petname: str
    goal: str
    size: int
    cohesion: float = 0.0  # mean cosine of members to centroid; precision gate
    span_days: float = 0.0  # calendar span first→last occurrence; recurrence velocity
    score: float = 0.0      # ranking signal (cross-project recurrence dominates)
    samples: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)


def _extract_text(content) -> str:
    """A user turn's content is a string or a list of typed blocks; keep text only."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return ""


def _is_noise(text: str) -> bool:
    t = text.lstrip()
    # '<' = harness wrappers; '[' = injected [Image: …] coordinate blocks; pasted shell.
    if not t or t[0] in "<[" or _SHELL_RE.search(text):
        return True
    low = t[:48].lower()
    if low.startswith(("ok ", "okay", "yes", "no ", "thanks", "ps c:")):
        return True
    hay = text.lower()
    if any(m in hay for m in _NOISE_MARKERS):
        return True
    # Multi-line paste dominated by shell/command output rather than prose.
    if text.count("\n") >= 3 and ("sudo " in hay or "$ " in text or "://" in text):
        return True
    return False


def iter_user_prompts(source: str | None = None) -> list[Prompt]:
    """Pull the user's own prompts out of every project log under `source`."""
    root = Path(source) if source else Path.home() / ".claude" / "projects"
    prompts: list[Prompt] = []
    for fp in glob.glob(str(root / "**" / "*.jsonl"), recursive=True):
        project = Path(fp).parent.name
        try:
            with open(fp, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or '"user"' not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") != "user":
                        continue
                    msg = obj.get("message") or {}
                    if msg.get("role") != "user":
                        continue
                    text = _extract_text(msg.get("content")).strip()
                    if MIN_CHARS <= len(text) <= MAX_CHARS and not _is_noise(text):
                        prompts.append(Prompt(text=" ".join(text.split()), project=project,
                                              ts=obj.get("timestamp", "")))
        except OSError:
            continue
    return prompts


def _slug(text: str, taken: set[str]) -> str:
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in _STOP]
    base = "-".join(words[:2]) or "task"
    name, i = base, 2
    while name in taken:
        name = f"{base}-{i}"
        i += 1
    return name


def _top_terms(texts: list[str], k: int = 2) -> list[str]:
    freq: dict[str, int] = {}
    for t in texts:
        for w in set(re.findall(r"[a-zA-Z]{3,}", t.lower())):
            if w not in _STOP:
                freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:k]]


def cluster(prompts: list[Prompt], min_cluster_size: int = 3, max_prompts: int = 4000):
    """TF-IDF + HDBSCAN over prompt text. Returns labels aligned to prompts, or raises."""
    try:
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        import hdbscan
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            f"discovery needs scikit-learn + hdbscan ({exc}). "
            "Install: pip install 'iceni[discovery]'"
        ) from exc

    texts = [p.text for p in prompts][:max_prompts]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                          min_df=2, max_features=4000)
    X = vec.fit_transform(texts)
    X = X.astype("float64")
    # L2-normalize so euclidean distance ranks like cosine (OQ2 cosine basis).
    from sklearn.preprocessing import normalize
    Xn = normalize(X).toarray()
    clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
    labels = clusterer.fit_predict(Xn)
    return labels, texts, Xn


def _cohesion(vectors) -> float:
    """Mean cosine of L2-normalized member vectors to their centroid direction.
    Near-duplicate clusters score ~0.6+; swept-up blobs score low — the gate."""
    import numpy as np
    centroid = vectors.mean(axis=0)
    norm = np.linalg.norm(centroid)
    if norm == 0:
        return 0.0
    return float((vectors @ (centroid / norm)).mean())


def _medoid(texts: list[str]) -> str:
    """Cheapest representative: the shortest prompt at/above the cluster's median length."""
    s = sorted(texts, key=len)
    return s[len(s) // 2]


def _span_days(timestamps: list[str]) -> float:
    """Calendar days between first and last occurrence (0 if single-session/unknown)."""
    from datetime import datetime
    ds = []
    for t in timestamps:
        if not t:
            continue
        try:
            ds.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
        except ValueError:
            continue
    return (max(ds) - min(ds)).total_seconds() / 86400.0 if len(ds) >= 2 else 0.0


def _rank_score(size: int, project_count: int, span_days: float, cohesion: float) -> float:
    """Rank by cross-project recurrence, not raw frequency (GPT+Kimi, unanimous).

    A prompt repeated across distinct projects over calendar time is a reusable
    workflow primitive; a high-frequency single-session burst is project noise.
      * project_count enters linearly — cross-project is the dominant signal.
      * frequency is log-damped so one busy project can't win on volume alone.
      * span_days adds recurrence velocity (a single session → factor 1.0, neutral).
      * cohesion (already gated) is a mild cleanliness multiplier.
    """
    import math
    freq = math.log(size + 1)
    time = 1.0 + math.log(1.0 + span_days)
    return freq * project_count * time * cohesion


def discover(source: str | None = None, *, min_cluster_size: int = 3, limit: int = 10,
             min_cohesion: float = 0.34, existing: set[str] | None = None
             ) -> tuple[list[Candidate], int]:
    """Return (ranked candidate aliases, total prompts scanned).

    `min_cohesion` is the precision gate: clusters whose members aren't genuine
    near-duplicates (low mean-to-centroid cosine) are dropped as false positives.
    """
    prompts = iter_user_prompts(source)
    if len(prompts) < min_cluster_size:
        return [], len(prompts)
    labels, texts, Xn = cluster(prompts, min_cluster_size=min_cluster_size)
    projects = [p.project for p in prompts][:len(texts)]
    tstamps = [p.ts for p in prompts][:len(texts)]

    groups: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        if lab == -1:  # HDBSCAN noise — the precision filter doing its job
            continue
        groups.setdefault(int(lab), []).append(i)

    taken = set(existing or set())
    cands: list[Candidate] = []
    for lab, idxs in groups.items():
        coh = _cohesion(Xn[idxs])
        if coh < min_cohesion:  # low-cohesion blob → reject (false positive)
            continue
        members = [texts[i] for i in idxs]
        proj = sorted({projects[i] for i in idxs})
        span = _span_days([tstamps[i] for i in idxs])
        terms = _top_terms(members, 2)
        petname = _slug(" ".join(terms) or members[0], taken)
        taken.add(petname)
        cands.append(Candidate(
            petname=petname,
            goal=_medoid(members),
            size=len(members),
            cohesion=round(coh, 2),
            span_days=round(span, 1),
            score=round(_rank_score(len(members), len(proj), span, coh), 2),
            samples=members[:3],
            projects=proj,
        ))
    # Cross-project recurrence over time, not raw frequency (the Phase II ranking fix).
    cands.sort(key=lambda c: -c.score)
    return cands[:limit], len(prompts)


def candidate_to_intent(c: Candidate):
    """Build a model-agnostic Intent from a confirmed candidate (no style hints yet —
    Phase III live calibration fills those from real per-model execution feedback)."""
    from .intent import Intent
    goal = c.goal if c.goal.endswith((".", "?", "!")) else c.goal + "."
    return Intent(goal=goal, inputs=["{{input}}"], constraints=[], outputs={}, style_hints={})
