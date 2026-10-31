"""검증된 공개자료만 검색하는 소형 로컬 RAG 리트리버.

개인 사용자 기록은 인덱싱하지 않는다. 형태소 분석기 설치 없이 한글을
검색하기 위해 문자 bigram/trigram TF-IDF + 행사/관계 메타데이터를 사용한다.
통계 액수 적용 가능 여부는 벡터 유사도가 아니라 구조화된 조건으로 판별한다.
"""
from __future__ import annotations
from collections import Counter
import json
import math
from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def grams(value: str) -> Counter[str]:
    text = re.sub(r"\s+", "", value.casefold())
    # 영문/한글/숫자를 분리하지 않고 일관된 문자 n그램을 계산한다.
    return Counter(text[i:i + n] for n in (2, 3) for i in range(max(0, len(text) - n + 1)))


class KnowledgeBase:
    def __init__(self, path: Path | None = None):
        self.data = json.loads((path or DATA_DIR / "knowledge_base.json").read_text(encoding="utf-8"))
        self.documents = self.data["documents"]
        self.by_id = {d["id"]: d for d in self.documents}
        self.tf = [grams(" ".join([d["title"], d["text"], *d["keywords"]])) for d in self.documents]
        df = Counter(g for counter in self.tf for g in counter)
        n = len(self.documents)
        self.idf = {g: math.log((n + 1) / (count + 1)) + 1 for g, count in df.items()}
        self.norms = [math.sqrt(sum((1 + math.log(v)) ** 2 * self.idf[g] ** 2 for g, v in vec.items())) or 1.0 for vec in self.tf]

    def eligible_amount_source(self, *, event_type: str, relationship: str, attendance_with_meal: bool | None):
        # 설문이 조사한 실제 조건과 정확히 일치할 때만 사용.
        for doc in self.documents:
            if not doc["can_anchor_amount"] or event_type not in doc["event_types"]:
                continue
            if doc["relationship_tag"] != "전체" and doc["relationship_tag"] not in relationship:
                continue
            if doc["attendance_condition"] == "attend_with_meal" and attendance_with_meal is not True:
                continue
            return doc
        return None

    def retrieve(self, query: str, *, event_type: str | None = None, relationship: str = "", legal_risk: bool = False, top_k: int = 4) -> list[dict]:
        q = grams(query)
        qnorm = math.sqrt(sum((1 + math.log(v)) ** 2 * self.idf.get(g, 1) ** 2 for g, v in q.items())) or 1.0
        out = []
        for i, doc in enumerate(self.documents):
            if doc["source_type"] == "legal_guidance" and not legal_risk and not any(t in query for t in ("청탁", "공무원", "공직", "법령", "직무")):
                continue
            if event_type and event_type not in doc["event_types"]:
                continue
            dot = sum((1 + math.log(q[g])) * self.idf.get(g, 1) * (1 + math.log(self.tf[i][g])) * self.idf.get(g, 1) for g in q if self.tf[i].get(g))
            cosine = dot / (qnorm * self.norms[i])
            boost = 0.08 if event_type and event_type in doc["event_types"] else 0.0
            boost += 0.12 if relationship and doc["relationship_tag"] in relationship else 0.0
            score = round(cosine + boost, 5)
            if score <= 0:
                continue
            out.append({"id": doc["id"], "title": doc["title"], "publisher": doc["publisher"],
                        "url": doc["url"], "published_at": doc["published_at"], "source_type": doc["source_type"],
                        "excerpt": doc["text"], "score": score,
                        "amount_reference_eligible": False})  # 검색 단계만으로 금액 적용 확정 금지
        return sorted(out, key=lambda d: (-d["score"], d["id"]))[:top_k]


KB = KnowledgeBase()
