"""Deterministic BM25 baseline without native vector dependencies."""
from __future__ import annotations

import math
import re
from collections import Counter


def tokens(text: str) -> list[str]:
    result = []
    for part in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", part):
            result.extend(part[i:i+2] for i in range(max(1, len(part)-1)))
        else:
            result.append(part)
    return result


class SparseRetriever:
    def __init__(self, evidence: list[dict], k1: float = 1.5, b: float = 0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("invalid BM25 parameters")
        self.rows = sorted(evidence, key=lambda row: row["evidence_id"])
        self.k1, self.b = k1, b
        self.frequencies = [Counter(tokens(row["normalized_claim"] + " " + row["verbatim_text"] + " " + " ".join(row["keywords"]))) for row in self.rows]
        self.lengths = [sum(counts.values()) for counts in self.frequencies]
        self.average = sum(self.lengths) / len(self.rows) if self.rows else 0
        self.df = Counter(term for counts in self.frequencies for term in counts)

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict, float]]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        hits = []
        for row, counts, length in zip(self.rows, self.frequencies, self.lengths):
            score = 0.0
            for term in set(tokens(query)):
                frequency = counts[term]
                if frequency:
                    idf = math.log(1 + (len(self.rows)-self.df[term]+0.5)/(self.df[term]+0.5))
                    score += idf * frequency * (self.k1+1) / (frequency+self.k1*(1-self.b+self.b*length/self.average))
            if score > 0:
                hits.append((row, score))
        return sorted(hits, key=lambda hit: (-hit[1], hit[0]["evidence_id"]))[:top_k]
