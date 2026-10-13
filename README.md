# KoreanSAT Agent Database

한국 대학수학능력시험·모의평가의 **메타데이터, 교육과정 정책, 기출 원본 링크, 코호트 연구용 스키마** 및 Python 수집·검색 도구.

> **License split:** Python code & original tooling = **GPL-3.0-only**, including commercial redistribution under GPL rules. **Project-created research/metadata compilation** = **CC BY-NC 4.0** (noncommercial, subject to underlying rights). **KICE, EBS/EBSi, Megastudy original materials** retain their original rights; the repo does not license, redistribute, or embed their copyrighted exam PDFs, texts, explanations, cutouts, or proprietary aggregate scores.

## Coverage

- Original source catalog: **7,200 EBSi exam records** (factual title/subject/date and external source links), **123 KICE document records**.
- Curriculum periods: 7차, 2007/2009/2015/2022 개정 and national implementation milestones.
- National CSAT structural eras, **2022–2027 공통+선택**, **2028 통합형**; subjects in `research/csat_subject_scope.csv`.
- Cohort table **1994–2028** with missing counts/skill measurements explicitly `NULL`; no unsupported year-to-year 'student ability' assertions.
- Per-item PDF clipping integration: `scripts/clip_question.py` (explicit page and bounding box; local images only, rights confirmation required).
- Separate Megastudy statistics integration script retains its *actual publisher and sample frame*; its source values are never relabeled as KICE nationwide correct rates.


**Year convention:** `calendar_year` = year of EBSi mock administration; `admission_year` = projected university entry year for grade 1/2/3 (grade 1: +3, grade 2: +2, grade 3: +1). It is NOT a claim that a grade 1/2 mock is the official CSAT for that university year.

## Ready-made metadata DB

The repository includes `data/research_catalog.sqlite.gz`, a reproducible bibliographic SQLite catalog with 7,200 exam records, 17,915 source-asset links and 123 official document records. It does **not** contain copied exam questions or solutions.

```bash
gzip -dk data/research_catalog.sqlite.gz
python scripts/validate_research.py --catalog data/research_catalog.sqlite
```

## Setup

```bash
python -m pip install -r requirements.txt
# Load standalone research + factual historical exam-catalog links from an original local .skill file
python scripts/build_research_catalog.py --source-skill ./suneung-agent-database-1.skill --out ./workspace/research_catalog.sqlite
python scripts/validate_research.py --catalog ./workspace/research_catalog.sqlite
```

For research without the original archive:

```bash
python scripts/build_research_catalog.py --out ./workspace/research_catalog.sqlite
```

Optional: provided data links may require their own rights review and access permissions. Programmatic EBSi/KICE import scripts are in `scripts/`; do not bypass authentication, robots/terms, rate limits, or rights restrictions. `scripts/integrate_megastudy.py` consumes a separate **locally obtained** data source and is not part of the source catalog.

## File map

- `SKILL.md` — AI-agent querying and source fidelity guidelines.
- `research/` — official-source registry, verified milestones, broad cohort/year index, subject regime tables.
- `scripts/build_research_catalog.py` — normalized SQLite data research and optional 7,200+ official/exam link import.
- `scripts/clip_question.py` — manual page+bounding-box PDF crop/link tool, **never publish clipped third-party question images without permission**.
- `scripts/validate_research.py` — integrity, count, provenance/links/curriculum tests.
- `scripts/crawl_ebsi.py`, `crawl_kice_official.py`, `retry_network_ebsi.py`, `build_suneung_agent_db.py`, `parse_question_items.py`, `integrate_megastudy.py`, `index_question_items.py` — original code with portable defaults, HTTPS verification enabled.
- `.env.example` — dummy credential placeholders. Set locally; no real login/secret is included in the published project.

## Research warnings

1. Original `question_items` extraction may merge two-column PDF question text into wrong items. Reindex/re-crop and visually validate before use.
2. School curriculum applicability is by **cohort**, not the year named in the reform. 2015 → first full graduated CSAT cohort 2021, 2022 → 2028.
3. 1994학년도 수능 was conducted twice in 1993; academic and calendar year differ.
4. Megastudy correct-rate data are calculated from its **scoring-service users** and should not be represented as an official nationally representative sample.
5. Source work copyrights and noncommercial data constraints remain even when code is GPL. See `licenses/DATA-LICENSE.md`.

## Extended verified research (2026-10-13)

- `research/verified_policy_transitions.csv`: 19 source-linked, area-by-area policy transitions (2014 A/B, 2021 curriculum transition, 2022 choices, 2028 integrated exam and August mock).
- `research/COHORT_EVIDENCE_AND_METHOD.md`: official-applicant vs actual-sitter differentiation, cohort ability comparison method, evidence gaps.
- `research/RIGHTS_AND_PUBLICATION.md`: item-level publication permissions, EBS educator license scope, Megastudy/KICE provenance split, dummy ENSI credentials.
- `scripts/import_official_attendance.py`: import a legally downloaded KICE official CSV into the **local** SQLite research catalog; 1994 two sessions remain separate, no invented ability or student-status metrics.
- `scripts/link_clips_to_items.py`: hash-check/visual-review gate, then map authorized private PDF clips to exact `question_items.item_id` using paper identifiers. It never publishes images.

```bash
# Official CSV: obtain from https://www.data.go.kr/data/15098904/fileData.do
python scripts/import_official_attendance.py --catalog workspace/research_catalog.sqlite --csv workspace/official_kice_attendance.csv
python scripts/import_official_attendance.py --catalog workspace/research_catalog.sqlite --csv workspace/official_kice_attendance.csv --apply

# After crop images are manually inspected, change image_assets.review_status to 'approved'
python scripts/link_clips_to_items.py --catalog workspace/research_catalog.sqlite --agent-db workspace/suneung_agent.sqlite
python scripts/link_clips_to_items.py --catalog workspace/research_catalog.sqlite --agent-db workspace/suneung_agent.sqlite --apply
python -m unittest discover -s tests -v
```

These are *tools and researched milestones*, not a claim that all years have official ability statistics or that 161,024 original questions have been image-clipped.

## Credits & References

Based on KICE examination and Ministry of Education official materials: see `research/source_registry.json` and `research/RESEARCH_NOTES.md`. Not affiliated with KICE, EBS or Megastudy.
