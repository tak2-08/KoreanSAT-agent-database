---
name: suneung-agent-database
description: Korean CSAT and mock-exam tutoring skill for instantly identifying exact past papers, mock-exam systems, score cutoffs, exam difficulty, composition, official study guidance, and preparation strategies from bundled EBSi/KICE data. Use for 수능·모의평가 questions, precise past-paper retrieval, grade-cut analysis, difficulty/composition analysis, study planning, data refresh, or building a low-token exam agent.
---

# 수능 에이전트 데이터베이스

## 지향점

수험생이 “어떤 시험의 몇 년도 몇 월 몇 과목인가?”, “이 시험의 등급컷과 난이도는?”, “이 단원과 유사한 정확한 기출을 찾아 달라”, “수능까지 무엇을 어떻게 준비할까?”라고 물었을 때 에이전트가 긴 원문을 모두 읽지 않고도 즉시 근거를 찾아 답하도록 한다.

EBSi 기출자료와 한국교육과정평가원 공식 자료를 시험·파일·공식문서·출처 관계로 SQLite/FTS5에 통합한다. 모든 답변에는 가능한 한 연도, 시험 종류(본수능/모의평가/예비시행), 월, 영역·과목, 출처를 함께 제시한다.

## 에이전트가 제공해야 할 핵심 능력

- **정확한 기출 검색**: 연도·월·시험 종류·영역·과목·문항 자료 유형으로 문제지, 정답, 해설을 특정한다.
- **시험 체계 안내**: 수능과 6·9월 모의평가, 교육청 학력평가, 예비시행을 구분하고 시행 주체·대상·범위를 설명한다.
- **등급컷 조회**: 원점수·표준점수·백분위·등급을 혼동하지 않고 시험·과목·연도를 고정해 조회한다.
- **난이도·구성 분석**: 공식 분석·오답률·문항 구성·출제 범위를 근거로 설명하며, 단순 인상과 공식 수치를 구분한다.
- **준비 전략**: 학습 안내서와 기출 흐름을 근거로 진단→우선순위→주간 계획→재평가 순서의 실행 가능한 조언을 만든다.
- **근거 추적**: 답변의 수치와 추천 기출을 `sources`, `exams`, `assets`, `official_docs`, `relations`까지 역추적한다.
- **문항 단위 검색**: 특정 연도·월·과목의 특정 번호 또는 번호대와 문제·정답·해설·정답률을 함께 조회한다.

## 표준 워크플로

1. 작업 디렉터리를 정한다. `DB_ROOT` 아래에 원본 DB와 파일을 보관한다.
2. EBSi를 수집한다. `scripts/crawl_ebsi.py`로 목록·메타데이터·등급컷·오답률·총평을 수집한다. 기존 DB를 재사용해 중단 후 재개한다.
3. 평가원 공식 자료를 수집한다. `scripts/crawl_kice_official.py`로 보도자료, 수능 관련 보고서, 기출·모의평가, 시행계획, 학습 방법 안내, Q&A, 예시문항을 수집한다.
4. 다운로드를 검증한다. `local_path`, HTTP 상태, 바이트 수, SHA-256을 확인한다. 404는 원본 부재로 분류하고 네트워크 오류와 섞지 않는다.
5. 네트워크 오류만 재시도한다. `scripts/retry_network_ebsi.py`를 실행한다. 404는 재시도하지 않는다.
6. 통합 DB를 만든다. `scripts/build_suneung_agent_db.py`로 기본 관계형 DB를 생성한다.
7. 문항을 파싱한다. `scripts/parse_question_items.py`로 문제지·해설지 PDF에서 문항 번호, 문제 텍스트, 정답, 해설을 `question_items`에 재개형으로 적재한다. 정답률은 원천 통계가 있을 때만 채우고 추정하지 않는다.
8. **선택 사항:** 별도 권한 및 이용조건을 확인한 메가스터디 통계 DB가 있다면 이를 연결한다. `scripts/integrate_megastudy.py`로 메가스터디 문항별 정답·정답률과 등급컷을 원천 보존하고, 연도·월·학년·과목 기준으로 `question_items`에 매핑한다.
9. 문항 검색 인덱스를 갱신한다. `scripts/index_question_items.py`로 문항 메타데이터와 짧은 지문 prefix만 `question_search`와 압축 JSONL에 반영한다. 전체 지문·해설은 `question_items`에서 `item_id`로 가져온다.
10. 검증한다. `PRAGMA integrity_check`, FTS 검색, 레코드 수, 오류 분류, 파일 존재 여부를 확인한다.

## 실행 예시

```bash
python3 scripts/crawl_ebsi.py --out "$DB_ROOT/data"
python3 scripts/crawl_kice_official.py --out "$DB_ROOT/data/kice_official" --workers 20
python3 scripts/retry_network_ebsi.py --out "$DB_ROOT/data" --workers 20 --attempts 3
python3 scripts/build_suneung_agent_db.py --root "$DB_ROOT"
python3 scripts/parse_question_items.py --root "$DB_ROOT" --workers 8
python3 scripts/integrate_megastudy.py --out "$DB_ROOT/suneung_agent.sqlite" --mega "$MEGA_ROOT/final/megastudy_suneung_tutor.sqlite"
python3 scripts/index_question_items.py --db "$DB_ROOT/suneung_agent.sqlite"
```

긴 수집 작업은 중복 실행하지 말고 로그와 프로세스를 먼저 확인한다. SQLite WAL 파일이 있으면 동일 DB에 병렬 쓰기를 추가하지 않는다.

## 데이터셋 사용 및 배포 범위

이 공개 저장소에는 **에이전트 지침과 데이터 수집·통합·검색 코드만** 포함됩니다. 문제 본문·해설, EBSi·메가스터디 통계와 사전 생성된 SQLite/JSONL 데이터는 제3자 권리 및 별도 이용 조건을 고려해 포함하지 않습니다.

실제 질의에 사용할 데이터베이스는 사용자가 관련 사이트의 이용약관·저작권 및 재배포 제한을 확인한 후 합법적으로 직접 구축해야 합니다. 스크립트는 데이터 수집을 자동화하지만, 모든 자료의 수집이나 상업적 재활용에 대한 허락을 보증하지 않습니다. 상세 경로는 [references/dataset_manifest.md](references/dataset_manifest.md)를 참고하세요.

기본 통합 DB 위치는 `$DB_ROOT/suneung_agent.sqlite`이며, 원천 DB는 `$DB_ROOT/data/`에 생성됩니다. 

## 통합 스키마

- `sources`: EBSi, KICE 등 출처
- `exams`: 연도·월·등급·영역·과목·시험 메타데이터
- `assets`: 문제지·정답·해설지 URL, 로컬 경로, 상태, 해시
- `question_items`: 문항 번호, 소문항, 영역, 지문, 선택지, 정답, 정답률, 난이도, 해설
- `official_docs`: 평가원 보도자료·분석서·학습 안내서와 첨부파일
- `mega_answer_rates`: 메가스터디 문항별 정답·난이도·정답률·선택지별 응답률 원천
- `mega_cut_scores`, `cut_scores`: 메가스터디 등급컷 원천과 통합 조회 테이블
- `relations`: 시험-파일-공식자료 연결
- `texts`, `texts_fts`: 저토큰 제목/본문 검색용 FTS5 인덱스

## 검색 원칙

```sql
SELECT exam_id, year, month, subject, title
FROM exams WHERE year=? AND subject LIKE ? ORDER BY month;

SELECT asset_type, url, local_path, bytes
FROM assets WHERE exam_id=? AND error IS NULL;

SELECT t.entity_type,t.entity_id,t.title
FROM texts t JOIN texts_fts f ON f.rowid=t.text_id
WHERE texts_fts MATCH ? LIMIT 20;

-- 문항 개념 검색: 검색 결과의 rowid를 question_items.item_id로 연결
SELECT rowid,year,month,subject,question_no,answer,correct_rate
FROM question_search WHERE question_search MATCH ? LIMIT 20;

-- 특정 시험의 번호대와 문항별 정답률/정답
SELECT e.year,e.month,e.subject,e.title,q.question_no,q.subquestion_no,
       q.answer,q.correct_rate,q.answer_source,q.correct_rate_source,
       q.difficulty,q.stem_text,q.solution_text
FROM question_items q JOIN exams e ON e.exam_id=q.exam_id
WHERE e.year=? AND e.month=? AND e.subject LIKE ?
  AND q.question_no BETWEEN ? AND ?
ORDER BY q.question_no,q.subquestion_no;
```

검색 결과를 `relations`로 확장해 관련 문제지·정답·해설·평가원 분석자료를 함께 가져온다. 긴 PDF/HWP/XLSX 원문을 먼저 전부 모델 문맥에 넣지 말고 제목·메타데이터·FTS로 좁힌 뒤 필요한 파일만 읽는다. `question_search`는 저토큰 후보 탐색용이며, 최종 답변 직전에 `question_items`에서 필요한 문항의 전체 지문과 해설만 읽는다.

## 질의별 응답 절차

### 정확한 기출 찾기

1. 연도·월·시험 종류·영역·과목을 먼저 확정한다.
2. `exams`에서 후보를 좁힌다.
3. `assets`에서 `problem`, `answer`, `solution` 유형을 연결한다.
4. 자료가 여러 시험에 중복되면 `paper_no`, 제목, 시험일을 대조해 하나만 선택한다.

### 등급컷·난이도·구성

1. 본수능, 평가원 모의평가, 교육청 학력평가를 구분한다.
2. 원점수/표준점수/백분위/등급 중 사용자가 묻는 지표를 고정한다.
3. 공식 등급컷·오답률·분석서가 있으면 우선 인용한다.
4. 공식 수치가 없을 때만 “추정” 또는 “자료 미확인”으로 명시하고 체감 난이도를 확정값처럼 표현하지 않는다.

### 수험생 학습 조언

1. 목표 시험일과 현재 성취도, 선택과목, 취약 영역을 확인한다.
2. 관련 기출과 평가원 학습 방법 안내를 검색한다.
3. 개념 보완→기출 훈련→시간 제한 풀이→오답 재학습의 순서로 계획한다.
4. 계획에는 자료명, 시험 연도, 문제 범위, 재평가 시점을 넣어 재현 가능하게 한다.

### 특정 번호대 검색

1. 연도·월·시험 종류·과목을 `exams`로 확정한다.
2. `question_items.question_no BETWEEN 시작 AND 끝`으로 번호대를 제한한다.
3. `answer`, `solution_text`, `correct_rate`를 함께 가져온다.
4. `correct_rate`가 NULL이면 해당 문항의 정답률이 아직 구조화되지 않은 것이므로 PDF/원본 통계에서 추가 확인하고 추정하지 않는다.

## 답변 품질·출처 규칙

- 원점수·표준점수·등급컷은 연도와 시험 종류(본수능/모의평가)를 명시한다.
- 평가원 공식 자료를 우선 근거로 삼고, EBSi는 기출 파일과 메타데이터 근거로 사용한다.
- 다운로드 오류 파일은 존재한다고 말하지 않는다. `HTTP 404`는 “원본 링크 확인 필요”로 표시한다.
- 대학별 합격선·충원·등록 결과는 평가원 수능 자료와 구분한다. 대학 또는 대교협 공식 자료가 없으면 확정 수치로 제시하지 않는다.
- 원문에 없는 정답·해설·통계를 생성하지 말고, 필요하면 “자료에서 확인되지 않음”이라고 답한다.

## 번들 스크립트

- `scripts/crawl_ebsi.py`: EBSi 색인·통계 수집
- `scripts/crawl_kice_official.py`: 평가원 공식 게시판과 상세 첨부파일 수집
- `scripts/retry_network_ebsi.py`: 404를 제외한 네트워크 실패 재시도
- `scripts/parse_question_items.py`: 문제지·해설지 PDF의 문항 단위 파싱·적재
- `scripts/integrate_megastudy.py`: 메가스터디 문항별 정답·정답률·등급컷 연결
- `scripts/index_question_items.py`: 문항을 FTS5·JSONL 검색 인덱스에 반영
- `scripts/build_suneung_agent_db.py`: 관계형 SQLite·FTS5·JSONL 통합 생성

## 기본 검색 예시

```bash
sqlite3 "$DB_ROOT/suneung_agent.sqlite" \
  "SELECT exam_id,year,subject,title FROM exams WHERE year=2024 LIMIT 20;"
```

## 라이선스

이 저장소의 자체 제작 코드와 문서는 `GPL-3.0-only`로 배포됩니다. 제3자 웹사이트에서 수집하는 콘텐츠·문항·해설·통계에는 이 라이선스가 적용되지 않습니다.
