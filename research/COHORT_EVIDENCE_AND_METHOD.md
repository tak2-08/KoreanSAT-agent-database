# 학년도별 응시집단·학력 특성: 실증 데이터 설계

## 검증된 제도 전환

`verified_policy_transitions.csv`는 교육부·평가원·정부 정책브리핑의 확인 가능한 문서에 대응하는 **시점별 변경 사건**이다. 학교 교육과정 고시연도, 고교 진입연도, **수능 학년도**를 동일하게 다루지 않는다. 1994학년도는 1993년에 2회 시행되었으며, 2028학년도는 2027년 시행 예정이다. 각 과목의 교육과정과 출제범위는 학년도별 시행계획을 우선한다.

### 정확한 전환 예시

| 수능 학년도 | 특이점 | 근거 |
|---|---|---|
| 2014 | 국어·영어 A/B 수준별 시험, 탐구 최대 3→2과목, 생활과 윤리·동아시아사 신설 | https://www.korea.kr/briefing/policyBriefingView.do?newsId=148770380 |
| 2017 | 한국사 필수화 (후속 시행계획과 교차검증) | https://www.moe.go.kr/boardCnts/view.do?boardID=294&boardSeq=80163&lev=0&m=020402 |
| 2018 | 영어 절대평가 | https://www.moe.go.kr/boardCnts/view.do?boardID=294&boardSeq=80163&lev=0&m=020402 |
| 2021 | 한국사를 제외한 영역에서 2015 개정 교육과정 첫 적용; 수학 가형에 기하 제외 | https://www.moe.go.kr/boardCnts/view.do?boardID=294&boardSeq=81446&lev=0&m=020402 |
| 2022 | 국어·수학 공통+선택 체제 도입 | https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=78242&lev=0 |
| 2028 | 국어·수학 선택 폐지, 통합사회·통합과학 필수, 하반기 모평 8월 실시 | https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=103113&lev=0&m=020402 |

## 모집단의 성격을 분리

1. **지원 인원**은 원서 접수자, **응시 인원**은 실제 시험에 참가한 인원이다. 지원자의 재학생/졸업생 구성이 실제 응시자의 구성과 동일하다고 가정하지 않는다.
2. **현역 학생**(일반적으로 고3), 졸업생, 검정고시 등의 항목은 원자료가 따로 제공할 때만 분리한다. 1994학년도는 두 시험을 합산해 하나의 응시 인원으로 만들지 않는다.
3. 평가원 공공데이터 `한국교육과정평가원_대학수학능력시험 연도별 응시현황_20251231`는 1994학년도부터 학년도·시험일정·지원인원·응시인원·응시율을 제공한다. **재학생/졸업생 인원이나 동일척도 학력 지표는 그 파일의 항목에 없다.** 공개조건은 공공누리 제2유형이다. https://www.data.go.kr/data/15098904/fileData.do
4. 2014학년도 수능 시행 당시 공식 **지원자** 650,747명 중 재학생 지원자 509,081명, 졸업생 등 141,666명이었다. 실제 **응시자** 구분 통계로 전환해서는 안 된다. https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=339&boardSeq=51265&lev=0&m=020601
5. `scripts/import_official_attendance.py`는 사용자에게 허용된 경로로 받은 공공 CSV를 읽어 고유한 **시험 회차 단위**로 적재한다. 같은 학년도 2회 시행은 별도 행이다. 학년도별 집계는 1회 시행 연도에 한하여 자동 보완한다.

## 학년도 간 '실력' 비교가 어려운 이유

- 과목 선택자 집단, 응시/지원 기준, 재수생 비중, 문항 수·범위·난도, 성적 산출 체계가 바뀐다.
- 다른 연도의 같은 원점수/등급컷은 동등한 잠재 실력을 뜻하지 않는다.
- 메가스터디 **채점 서비스 이용자**의 정답률·선지 응답률은 전국 응시자 통계가 아니다. 표본의 자기선택과 시간대별 집계 변화를 명시한다.
- 비교가 꼭 필요하다면 동일 과목에 공통문항/동일척도 연결(IRT 등)과 표준오차, 구성집단의 특성, 층화 및 가중 방법, 민감도 분석을 제공한다.
- 각 학년도에 `relative_ability`를 값 없이 둔 것은 결함을 감춘 게 아니라, **관측 가능한 비교 지표가 아직 부족하다**는 명시적 결측이다.

## 향후 실증 연구의 최소 단위

`admission_year, exam_session, applicant_n, taker_n, current_student_applicant_n, current_student_taker_n, graduated_taker_n, subject_selector_n, mean_standard_score, sd, difficulty_index, sample_frame, confidence_interval, source_url, publication_date, verified_by, quality_flag`를 **구분해** 수집한다. 일부만 제공될 경우 나머지는 NULL. 2027학년도 이전/이후 제도변경은 서로 다른 평가 척도로 먼저 취급한다.
