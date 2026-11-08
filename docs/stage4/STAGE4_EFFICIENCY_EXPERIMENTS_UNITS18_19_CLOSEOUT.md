# Stage 4 효율 실험 Units 18–19와 R1 마감

## 현재 판정

2026-11-08에 Units 18–19 묶음 독립 검토와 R1 변경분의 보충 검토를 마쳤다. Unit18의 네 등록 판에서 1클릭 제한 개선을 확인했다. Unit19는 주 비교 기준에서 MIXED다. 두 후보와 R1 전달 코드는 output 영역의 실험 prototype이며 제품 반영은 DEFERRED다. Stage 4 전체 판정은 NOT_MERGED다.

이 문서 마감의 출발 HEAD는 `606a36316b125294f45d4a7cfb970eeadcdf381f`다. 현재 제품 source 365개는 동일하며 문서만 갱신한다. 새 문서 커밋으로 과거 시험·측정의 실행 HEAD를 소급하지 않는다. 이전 범위는 [Units12–17 마감](STAGE4_EFFICIENCY_EXPERIMENTS_UNITS12_17_CLOSEOUT.md)을 따른다.

## 두 후보의 범위

Unit18 `SAFE_COMPONENT_COVER_V1`은 현재 Q가 증명한 안전/지뢰 집합을 사용한다. 공유 FLAG 또는 표적이 겹치는 CHORD 성분 중 최대 10개 pivot·80개 안전 표적을 대상으로 준비 FLAG, 안전 FLAG 해제, CHORD, 남은 직접 OPEN의 총 명목 비용을 비교한다. c(J)는 선언한 정적 후보군의 비용이며 미래 flood·새 숫자·게임 전체의 최저 입력 수를 뜻하지 않는다.

Unit19 `SAFE_OPEN_REMAINING_COST_V1`은 Unit18을 기준으로 안전 OPEN 후보를 최대 8개 고른다. 공개 관측의 공동 사건에서 정확한 0 확률을 구하고, 0/비0 두 경우의 남은 안전 영역 비용을 비교한다. H=a+(1−p0)K_nonzero+p0K_zero는 기존 pivot과 고정 안전 영역의 명목 completion 모형이다. H나 K0, H−K0를 게임 전체 E[C]·E[X]·IOE 최적성 또는 실제 절약량으로 사용하지 않는다.

Q의 Unit10 합산 units와 Unit19 사건 계수의 legacy work는 별도 단위로 보존한다. 물리 FLAG는 확정 지뢰로 간주하지 않으며 숨은 배치·seed·진행 3BV·분리 클릭 카운터는 정책 입력이 아니다.

## 등록 네 판의 실제 결과

| 판 | 원 Q(Unit15) | Unit18 | Unit19 | 결과 |
| --- | ---: | ---: | ---: | --- |
| E01 | 163 | 163 | 158 | 세 경로 모두 WON |
| E02 | 174 | 173 | 175 | 세 경로 모두 WON |
| E03 | 3 | 3 | 3 | 세 경로 모두 LOST |
| E04 | 2 | 2 | 2 | 세 경로 모두 LOST |
| 승리판 C 합계 | 337 | 336 | 333 | 각 판 비증가 조건과 함께 판단 |

Unit18은 각 기존 승리판 C가 증가하지 않으며 합계가 1 감소해 BOUNDED_IMPROVEMENT_OBSERVED다. E02의 승리 IOE는 177/173이며 E01은 167/163이다.

Unit19는 Unit18 대비 E01에서 5 감소하고 E02에서 2 증가해 MIXED다. 승리 IOE는 각각 167/158, 177/175다. 합계 감소나 보조 Unit15 비교로 주 기준 미충족을 바꾸지 않는다. 패배판 IOE는 해당 없음이고 등록 X만 0이다.

같은 공개 상태 대조에서 Unit18의 첫 변경은 양쪽 C112로 다시 합쳐졌고, 두 번째는 같은 C153에서 시작해 174/173으로 끝났다. Unit19는 E01의 앞 구간에서 1 증가한 뒤 후반 6 감소, E02는 앞의 두 구간에서 각각 1 증가했다. 이는 저장 경로 대조이며 별도의 인과 효과 실험은 아니다.

## 묶음 독립 검토

- Unit15 342 + Unit18 341 + Unit19 338 = 1,021입력을 독립 엔진 모형으로 재생했다. 공개 관측, 승패, C, 3BV, IOE/X가 일치했다.
- Unit18 A 288·D 279, Unit19 A 279·D 282의 수학·선택 재계산이 일치했다. Unit18 A의 엄격 감소 6건은 모두 E02이며, 겹친 후반 관측을 독립 절약으로 더하지 않는다.
- Unit18 c(J)는 원자 입력 BFS 328건이 일치했다. Unit19 K는 공식 열거로 전 행이 일치했고 BFS는 override 25행의 93건을 대조했다. 나머지 K 행의 BFS는 예산 한도로 미실행이다.
- 사건 112호출 중 COMPLETE 110호출의 D/M과 공동 사건 186개의 W·p0를 모두 독립 재계수했다. INSUFFICIENT와 CANCELLED 각 1호출은 값이 null이고 점수에 연결되지 않았다.
- Unit19 oracle 99 lease의 states 1,715, layouts 132와 실제 미정산 예약 0을 확인했다. 모든 사건 호출이 COMPLETE였다고 표기하지 않는다.

## H1과 과거 실패 보존

Unit17 driver의 Fraction 직렬화 H1은 Unit18·19의 새 helper에서 stdlib-only 변환과 실제 최종 저장까지 독립 확인했다. 큰 정수는 문자열과 정수 두 표현을 수용해야 한다. Unit17 원본의 최종 envelope 실패와 PARTIAL/MIXED/미채택은 당시 이력으로 보존한다.

Unit18 첫 oracle 전개 스칼라는 UNKNOWN이며 정확 회계 축은 PARTIAL이다. 코드상 유효한 예약 상한 13,015와 복구 실제 5,677로 누적 상한 18,692를 확인했다. 이를 정확한 과거 전개 수로 바꾸지 않는다. 원 `focused_tests.py`의 empty-to-empty local_mismatch 진입점은 재사용하지 않고 보정된 경로를 사용한다.

Unit19 순수 집중 시험의 subset 1,064/896은 source 경로 재구성이다. 실제 관측된 정책 결정 계수와 oracle journal을 구분한다. Units18–19의 과거 명령·시험·집계 보정과 검토 도구 실패도 원본에 보존한다.

## RV-U18-01과 R1

원 검토는 빈 CHORD 그룹 전체를 건너뛰면 그 그룹이 처음 놓을 공유 지뢰 FLAG도 빠져 뒤 CHORD가 CHORD_PROOF에서 멈출 수 있다고 지적했다. 원 D에서는 발생하지 않았으며 위험 입력은 차단된다.

R1은 같은 root proof와 실제 이웃에서 다시 검증한 확정 지뢰 중, 아직 닫힌 표적이 있는 뒤 CHORD가 필요로 하는 FLAG만 원래 planned_index에 보존한다. 그 FLAG도 기존 원자 guard를 통과한다. 원 계획 밖 입력은 추가하지 않고, 필요 없는 준비와 빈 CHORD는 생략한다. c(J), K, H, 정책 선택은 변경하지 않았다.

7×5 합법 엔진 관측의 통제 수순에서 수정 전은 CHORD(2,0) 뒤 CHORD_PROOF로 멈췄다. 수정 후는 CHORD(2,0), FLAG(3,3), CHORD(4,3)으로 WON이며, 중간 빈 CHORD 입력 0·공유 FLAG 1·실제 3/명목 4다. 공개 숫자의 두 불연속 구간이 각각 전체 5지뢰를 소진하고 교집합이 지뢰벽 5칸임을 독립 확인했다. Q 결과 DTO와 J 선택은 통제 입력이다.

보충 검토의 RV-U18-01 판정은 **RESOLVED_FOR_CONTROLLED_SEQUENCE**다. 실제 상급판에서 정책이 그런 J를 선택하는지는 UNCONFIRMED다. 보존 FLAG 전후 guard는 통제 전이 검증이며, 이미 FLAG인 사례는 멱등성 통제 계획이다. 그 상태의 새 컴파일 결과라고 표기하지 않는다.

## R1 시험과 실행

고유 시험 38개는 최초 34/38과 실패 4개만의 보완 4/4로 통과했다. 총 case 실행은 42다. 잘못된 기대 사유 1개와 JSON 복사의 2.0→2 lexeme 손상 3개를 보정했으며 최초 실패·등록·helper를 보존했다. 원 request_id를 교체하거나 검증을 끄지 않았다.

R1 실제 엔진 입력은 99(setup 86 + macro 13), 통제 전이는 57(fixture 35 + 기존 trace 22)이다. 보충 검토는 실제 99와 trace 22를 독립 재생했고 macro receipt 31개에서 actual+skip+tail=nominal을 확인했다. Unit18 Q67/Q126의 수정 전·후 trace는 같고 Unit19 fallback도 같은 수정 클래스를 사용한다.

R1 START 2/2·Python image 4/4는 별도 예산이다. 원 Unit19의 2/3·4/6과 합친 물리 누적은 START 4·image 8·실제 엔진 입력 472다. 원 작업 기한·상한을 소급 변경하지 않는다. 두 R1 Job은 600초 timeout, 종료 요청 0, 최종 member 0과 소유 handle/pipe 정리를 기록으로 확인했다. 실제 모델/노력/속도, 검토 Fast 설정의 미노출 값은 UNCONFIRMED다.

## 남은 한계와 다음 범위

보존 FLAG 이후의 다른 flood가 뒤 CHORD 표적까지 열면 그 FLAG 1회가 결과적으로 불필요할 수 있다. 안전한 원 계획 입력이며 실제 원시로 시험되지 않은 비차단 한계다. 미래 최저 비용이나 일반 상급판 효율을 보장하지 않는다.

제품 source 반영, S/M/R 일반 상급판 평가, 메인 UI/worker 통합과 사용자·전시 노트북 수용은 별도 범위다. 다음 전략·비교는 따로 등록하며 이 마감으로 자동 실행하지 않는다. D0–D5/V1/frozen 정책·Model C·holdout·연구 승인 및 이전 실패 경계를 유지한다.

## 근거 위치

- Unit18 구현과 조율 확인은 `outputs/STAGE4_SAFE_COMPONENT_COVER_UNIT18_2026-11-08/` 아래에 있다.
- Unit19 구현 `codex_01`, R1 `codex_02`, 본 검토 `review_claude_01`, 보충 검토 `review_claude_02`는 `outputs/STAGE4_OPENING_COST_LOOKAHEAD_UNIT19_2026-11-08/` 아래에 있다.
- 각 REVIEW_REPORT_KO.md, FINDINGS.json, CROSSCHECK.json, INPUT_BINDING.json, REVIEW_LEDGER.json, OUTPUT_MANIFEST.json을 개별 범위로 읽는다. 현재 원본은 `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/`에 보존한다.
- 최종 문서·Git·Desktop recovery 영수증은 별도 closeout 폴더에서 확인한다. 이 문서는 문서 작성 당시 snapshot이다.
