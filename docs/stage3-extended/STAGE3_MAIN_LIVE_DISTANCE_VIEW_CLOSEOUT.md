# Main/Live 거리 관람·성능 진단·실행 도구 보완

기준일: **2026-11-06 (Asia/Seoul)**. 거리 기능과 보완분의 독립 검토는 범위 한정 수용이며 **제품 필수 수정 0, 보완분 실행계약·evidence 필수 보완 0**이다. 후속 검토된 최적화 반영 뒤 사용자는 이번 PC의 세 모드와 Replay 두 종료를 **“모두 통과”**로 수용했다. 전시 노트북은 PENDING이며 문서·Git·Desktop 마감은 준비 중이다. 후속 최적화의 별도 기준·이력은 [고정 6 CPS closeout](STAGE3_MAIN_LIVE_FIXED6_OPTIMIZATION_CLOSEOUT.md)을 따른다.

## 1. 판정과 현재 authority

| 대상 | 판정 | 범위 |
| --- | --- | --- |
| 원 본작업 `codex_01` | **전체 PARTIAL 유지** | 거리 기능·원시 산술·결속은 `review_claude_01`의 ACCEPT_BOUNDED. 당시 최상위 launcher 계약 미적용 이력은 보존 |
| 새 outer helper `codex_02` | **ACCEPT_BOUNDED** | 당시 정상·timeout·resume 전 중단 graph. 후속 fixed6 G01에서 실제 owner graph 조건을 확인했으며 모든 API 실패 경로 시험으로 확대하지 않음 |
| T1/T2 `codex_03` | **ACCEPT_BOUNDED** | offscreen Qt·제어 시계·fake actor의 새 3개 메서드/10개 하위 사례 |
| 원 main의 CR01-F03 라벨 | **ACCEPT** | 아래 네 상태를 분리하고 원 보고서·raw를 유지 |
| 사용자 native 수용 | **이번 PC 수용** | 후속 검토된 최적화 반영 뒤 세 모드 진행·중단 및 Replay 두 종료 후 설정 보존. 전시 노트북 확인은 별도 PENDING |

이 문서의 최초 작성 기준 HEAD = local origin/main = `dc711a7917edf3f00bbad26f710b5240c08d7f13`, branch `main`, staged 0, ahead/behind 0/0이고 당시 index SHA256은 `6a59514bcd13f0bf9018ea03913dcb7711bc0cea1aa67ed57b850e275403d285`였다. 후속 index 변화와 현재 반영은 고정 6 CPS closeout의 별도 receipt를 따른다. 각 실행 시점의 source/helper hash를 미래 commit으로 소급하지 않는다.

이 거리 단위의 제품 변경은 `ui_manager.py`, 새 `live_distance_pacing.py`, 새 `tests/test_live_distance_pacing.py`의 3경로다. 당시 최종 source manifest는 335행이며 `codex_03`은 테스트 파일만 추가 변경했다. 거리 테스트 SHA256은 `3a1c2be377f552b6af4792954bb5c0641af84716c41b773f1c91275f134d434a`다. 후속 최적화는 같은 source335 중 별도 4경로를 바꿨고, 전체 Git 마감은 source/tests6과 문서7을 묶는다. 문서를 테스트 실행 당시 상태로 가장하지 않는다.

## 2. 제품 관람 계약

Main/Live의 속도 선택에 **거리 기반**을 추가했다. 새 창 기본은 기존 **고정 간격 200 ms / 목표 5 CPS / Auto OFF**다. 고정값, 원 Model C 배속, 거리 배속은 현재 창에서 각각 보존한다. 전역 사용자 설정은 바꾸지 않는다.

거리 모드는 이미 선택된 다음 target과 기존 public/actual cursor 사이의 직선 칸 거리 `d`를 사용한다. 정책 cursor·후보 선택·추론·Model C 비용은 바꾸지 않는다. 진짜 cursor 부재만 `d=0`으로 처리하고 이유를 metadata에 남긴다.

`distance_view_log_v1`의 관람 기본안은 다음과 같다.

```text
base_ms = clamp(a + b × ln(1 + min(d, 16)), L, U)
a = 37.55779754656098
b = 189.88338306970934
L = 91.66666666666667 ms
U = 550 ms
view_ns = ceil(base_ms × 1,000,000 / rate)
```

배속은 0.05–8, 기본 1이다. Decimal precision 50/ROUND_HALF_EVEN의 sqrt·ln과 정확한 Fraction 나눗셈 뒤 ns 올림을 사용한다. `d=0`에서도 양수이고 거리가 증가하면 비감소, 배속이 증가하면 비증가한다. upper clamp는 약 13.861칸부터 적용되므로 16칸 cap보다 먼저 포화될 수 있다. 0.05배의 최대 관람 대기는 11초다.

계수 출처는 기존 `analysis/results/candidates.json`의 `/full_data_descriptive_fit/bounded_log`다. SHA256은 `412adaf2e434c25685659737cf5b22b1d4495517070f296bf6775fb12544ea40`, `FIT_PLAN.json`은 `d06712b09f58627d12c1f3b733afac9b4d31e5ce90ad9b76e31ef432950596a2`다. 제품에 작은 상수로 포함했으며 실행 중 사용자 outputs를 읽지 않는다. 기존 30판/5035전이/24 player 분석을 다시 적합한 것이 아니다. OOF log/bands 차이 0.792 ms, 긴 gap 제외 시 순위 반전, action UNKNOWN, d>16 표본 3이라는 한계를 유지한다.

관람 대기는 다음 target을 고른 뒤 시작한다. 실제 입력 간격에는 계산·통신과 K 검증 왕복도 포함된다. **거리 배속 2배가 실측 CPS 2배를 보장하지 않는다.** 이 기능은 관람 기본안이며 인간 운동 법칙·효과성·안정 처리량 상한의 증명이 아니다.

K는 관람 대기가 끝난 뒤 VALIDATE→ADMITTED로 진행한다. 긴 대기를 위해 permit이나 원 30/5/5/0.75초 cap을 늘리지 않는다. 마지막 비교→token→실제 입력 사이 무yield, 정확 ACK→NEXT, 취소·수동 인계·보드 변경의 예약 폐기를 유지한다. 가상 원형은 같은 관람 시간을 사용하고 OS 마우스나 Human trace에 합성 경로를 넣지 않는다.

새 metadata는 `live_input_records.distance_view`에만 있다. 원 `modeled_action_us`, `compute_ns`, `live_auto_totals`, wire v10, Replay event/schema/기록 시계는 유지한다. Simple의 `distance_view.run_id`는 UI Live 실행 상태 UUID이며 바깥 입력의 `run_id`는 policy owner가 없으면 null이다. 둘을 동일한 owner 식별자로 결합하지 않는다.

Simple의 기존 크기 범위와 V1/K의 기존 preset 지원 범위를 유지한다. 미지원 보드에서는 실효 고정 모드로 표시하고, 지원 보드로 돌아오면 보관한 거리 모드·선호를 복원한다. 새 V1/K custom 지원은 추가하지 않았다.

## 3. 성능 진단과 최적화 미채택

원 main은 같은 30×16/99 합성 공개 저부하 fixture에서 A 기준 6회, 렌더 후보 4회, 최종 C/D/E 12회, 합계 **22회 × 실제 입력 62개**를 수행했다. 각 run은 새 game/run/owner이며 warmup 2개와 steady 60개/내부 59 gap을 분리했다. policy 입력 1369개와 별도 Simple 1개, 총 Auto 1370개다.

`review_claude_01`은 22 run의 timing 944/944, wire·identity 22/22, 거리 E 248개와 family/native/Simple 6개 지점의 원시 값을 대조했다. 주 CPS `(N−1)/Auto-span`, Counters 전체 클릭/게임 시간, 완전 window peak는 별도다.

중복 Qt setter 생략 후보는 V1 평균 gap 16.19% 개선, LC1 9.57% 개선으로 관측됐다. 사전 LC1 10% 기준에 미달해 **미채택하고 원 renderer를 복원**했다. 최종 제품에는 이 성능 최적화가 없다. 최종 fixed0 차이를 채택 효과로 주장하지 않는다.

TRACE의 평균 gap 변화는 약 +9.05%/+8.74%, MIN 간 drift는 8.78%/6.43%다. 계측 영향과 시간 흔들림의 인과 분리는 **INSUFFICIENT**다. read.open·render의 inclusive 비용과 부모의 비중첩 anchor budget을 구분하며 native paint·CPU 비용은 미측정이다. 성공 read.open의 OS·백신·디스크 원인을 단정하지 않는다.

fixed 5/6 CPS의 own deadline 이전 입력은 0이고 최소 0.9P 계약을 확인했다. LC1 fixed6의 steady 약 5.724 CPS/95.4% 도달은 해당 조건의 관측이며 일반 안정 상한이 아니다. B1 동일 owner·설정별 60은 **NOT_SATISFIED**다. 후보 이름 B1과 이 측정 조건 B1을 혼동하지 않는다.

## 4. 실행 도구 보완과 과거 PARTIAL

원 `codex_01`의 상태는 다음과 같이 보존한다.

| 원 최상위 경계 | 상태 |
| --- | --- |
| suspended 생성 | NOT_APPLIED |
| helper 소유 outer Job | NOT_APPLIED |
| ambient/host Job 소속 | NOT_SAMPLED |
| outer conhost 신원 | NOT_IDENTIFIED |

이는 당시 하위 driver/worker의 포함·정리 근거를 무효화하지 않는다. 과거 process 누수가 있었다고 주장하지 않으며 새 실행으로 과거 라벨을 PASS로 바꾸지 않는다.

`codex_02`의 새 controller는 첫 소유 Python을 suspended 생성해 kill-on-close Job에 할당하고 membership을 확인한 뒤 한 번 resume한다. stdio만 명시적으로 상속하고 lifetime Job handle은 상속하지 않는다. 정상·timeout·예외 때 소유 Job/process의 종료·reap·pipe EOF·reader join·handle 종료를 확인한다.

P1 정상 6/6, P2 등록 timeout 6/6, P3 resume 전 중단 1/1과 `codex_03` T1T2 graph 3/3은 total=observed, active/member 0으로 독립 대조됐다. P3는 실제 API 실패가 아니라 할당·membership 성공 뒤 의도적으로 resume하지 않은 경우다. P2/P3의 exit238과 Python finally 미실행 가능성을 구분한다. 보완의 실제 OS graph 16개와 논리 Python 시작 6회는 다른 수치다.

신뢰 경계 밖의 PowerShell 컨트롤러·그 conhost·Add-Type compiler, 컨트롤러 강제 사망 및 모든 Win32 API 실패는 전수 검증하지 않았다. 이 거리 단위 종료 당시에는 **CR02-F04의 등록 owner 사례 1회 검증이 필요**했다. 후속 고정 6 CPS 단위의 G01에서 실제 owner 재사용을 검증했고 이후 graph 정리도 독립 대조했다. 과거 거리 단위의 owner 미실행 상태는 그대로 보존한다. 사용자 native 확인은 일반 Main 실행 경로다.

## 5. 테스트 버전과 독립 수용

- 원 거리 통합의 focused 85개와 이후 추가한 1개 메서드/14 subcase는 실행 당시의 각 tests bytes에 한정한다.
- `codex_03`의 새 3개 메서드/10 subcase는 T1 Simple 2 + V1/K 4, T2 view/validation × Replay 두 종료 4다. 기존 줄 삭제·기대 약화·skip은 없다.
- T1은 DISTANCE를 직접 선택하고 실제 지원 predicate를 사용했다. 미지원에서 실효 fixed·Auto 차단·선호 보존, 지원 복귀를 확인했다. Simple은 fixed4 CPS에서 실제 단위 입력/Replay 각1회를 확인했다.
- T2는 실제 Replay 진입·cancel drain·두 종료를 거쳐 Live로 복귀했다. 세대·세 선호·Auto/guess OFF·기본 미배치/동일 배치·옛 callback과 정상 fake actor permit의 무효를 확인했다.
- `review_claude_02`는 이 두 축과 새 helper, CR01-F03 라벨을 각각 ACCEPT_BOUNDED/ACCEPT로 판정했다. CROSSCHECK 38행은 MATCH 34, MISMATCH 0, NOT_VERIFIED 3, NOT_SAMPLED 1이다.

각 버전의 테스트 수를 최종 동일 bytes의 한 번의 전체 suite PASS로 합치지 않는다. offscreen Qt/fake actor 결과는 사용자 native 수용을 대신하지 않는다.

## 6. 선택 항목과 실패 이력

보충 검토의 제품 필수 수정 및 실행계약·evidence 필수 보완은 모두 0, 선택은 6이다.

| 선택 항목 | 현재 처리 |
| --- | --- |
| CR02-F01 catch 내부 Event 기록 실패 | 정리는 수행되지만 결과 파일이 없을 수 있다는 유지보수 한계 보존 |
| CR02-F02 생성→Job 할당 사이 ms 단위 창 | suspended 상태의 한계로 기록. 생성 시 Job 배정 강화는 미적용 |
| CR02-F03 끝 백슬래시 인수 quoting | 현재 인수에는 문제 없음. 인수 확장 시 보완할 유지보수 항목 |
| CR02-F04 새 controller의 실제 owner graph | 거리 단위에서는 미실행. 후속 고정 6 CPS G01에서 재사용 전 검증 조건 충족; 과거 실행을 소급 수용하지 않음 |
| CR02-F05 미시험 실패 경로·graph 밖 process | 위 실행 도구 절의 한정 범위를 유지 |
| CR02-F06 시간·시작 시각·종료 카운터 설명 | 아래 시각과 의미를 분리해 문서화 |

보완 시작 00:27:24Z부터 최종 manifest 01:11:56Z까지 대기 포함 약 44.54분, 두 active 구간 합계는 약 32.28분이다. `codex_03` 본문 33.85/21.58분은 01:01:14Z 중간 점검까지의 값이다. 컨트롤러 process 시작과 `controller_start` 기록 시각도 구분한다. Job의 `terminated=0`은 한도 위반으로 종료된 process의 카운터이며, TerminateJobObject가 호출되지 않았다는 뜻이 아니다.

원 main Python53/owner25, 읽기4/helper6/고유10과 원 실패를 보존한다. 보완 Python5+1=6, 읽기1+1=2/2, helper0/3, 고유2/4, 실제 owner0이다. 최초 Claude의 incident6/6과 중지한 600초 초과 스크립트·첫 실패 산출물, 다음 Claude의 새 incident0/3을 분리한다. 이전 검토의 추정 종료 시각과 project memory 쓰기 신고도 삭제하지 않는다.

이전 CR01 선택 8건도 일괄 CLOSED가 아니다. 제품 거리50자리/oracle80자리, Simple run_id 의미와 관람 배속 설명은 문서화했다. 미지원 거리 coverage는 T1에서 보완했고 숨김 tooltip·도달하지 않는 경로는 선택 유지보수로 남았다.

## 7. evidence와 다음 마감

로컬 evidence root는 `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\MAIN_LIVE_PERFORMANCE_DISTANCE_IMPLEMENTATION_2026-11-06`다.

| 묶음 | OUTPUT_MANIFEST SHA256 |
| --- | --- |
| codex_01 | `c47f02892c1c21b75704bccf171414b24d570c9f6d0a52c1e198fbe44673bc50` |
| review_claude_01 | `4d36b733b87fc94a666375ee80e58166b5b46ac5ff272439559cd1dfb54a6f31` |
| codex_02 | `72e05b14415c638b1357b47f89de2557216385e08b352503bebc5b1d6cc6096e` |
| codex_03 | `558dd824a342e738f7d5409110c7abf065ce9fe2b869432de0b2c7c7876e2591` |
| review_claude_02 | `c55224dea4d703fda86b7b6e524453ab2d376a2bce0cd031432e7a69666478f8` |

**현재 다음 단계는 관련 문서 확정 → source/tests와 문서의 한 묶음 commit/push → 실제 commit에 맞춘 Desktop recovery 교체·destination 검증이다.** 이번 PC native는 후속 최적화 반영 뒤 수용됐으며 전시 노트북은 별도로 남는다. 문서 작성으로 Git/배포 완료를 주장하지 않는다. 과거 Git·Desktop 교체 스크립트는 다시 실행하지 않는다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P 미승인을 유지한다. Phase2/R0-B/ActualE2는 미승인·미실행이며 frozen 정책·원 Model C·holdout `2,010,000..2,010,099`·금지 formal evidence는 열지 않는다. 과거 F02 NOT_VERIFIED·Qt shared FileDialog FAIL·TEMP NOT_VERIFIED도 그대로다. 새 package·Stage4·효과성 연구를 시작하지 않았다.
