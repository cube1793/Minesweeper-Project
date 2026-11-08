# Stage 4 Units24–26 실험용 S/M/R API와 F1 보완 마감

## 현재 판정

공개 indexed 커널, 공통 후속 정책 F, 모델 평가기와 S/M/R runtime API를 미연결 실험 코드로 보존한다. F1 보완은 독립 검토에서 **F1_FIXED_BOUNDED**로 수용됐다. **AVAILABILITY_NOT_MET / INTEGRATION_NOT_READY / 효율·실전 목적 차이 NOT_ESTABLISHED**를 유지한다. Stage4는 **NOT_MERGED**다.

| 축 | 범위와 판정 |
| --- | --- |
| 커널 안전·논리 | PASS_BOUNDED, 공개 proof 388개에서 오류 0건 |
| 커널 가용성 | 388/857, 목표 686 미달. 기존 339개 중 336개 유지, 신규 52개, 퇴행 3개 |
| 모델 계산 | 완료된 행·점수·선택 재현 PASS_BOUNDED |
| 모델 의미 | 원 F1 필수 문제 발생, 보완 후 F1_FIXED_BOUNDED |
| 모델 가용성 | 원 보고 4/18, 등록 F 기준 유효한 과거 완료 3/18. 수정 후 큰 모델 미측정 |
| runtime 전달 | 실제 입력 1,520회 재생. S 안전 위반 0건, stale 추가 입력 0건 |
| 실전 효율·목적 차이 | NOT_ESTABLISHED, 원 16회 모두 LOST |
| 운영 통합 | INTEGRATION_NOT_READY, Main/worker/UI/Replay 미연결 |

실제 구현·시험·비교·보완의 출발 HEAD는 `ba3d140660ad57f300cbd9f1333b983d661aefee`다. source 369개에 신규 6파일을 더한 현재 source는 375개다. 기존 `stage4_public_kernel.py`의 변경은 새 work-version을 허용하는 한 줄이다. 신규 모델과 시험은 F1 보완 bytes를 사용한다. 마감 대상은 source/tests 7경로와 문서 6경로, 합계 13경로다. 출발 tracked는 452개, 예정 tracked는 459개다. 이후 commit을 과거 시험 HEAD로 소급하지 않는다.

## 코드와 공개 정보 경계

- `stage4_runtime_kernel.infer_public_indexed`는 기존 KernelRequest/KernelResult와 공개 규칙을 재사용한다. 불변 식, 정규화, postings/anchors/queue로 관계를 처리하며 `prepaid_indexed_immutable_relations_v1`로 작업을 기록한다. 기본 한도는 480칸, 제약 2,048개, 파생 1,024개, work 500,000, 협력적 시간 검사 2초다. 완료 전 proof 검증도 work에 포함된다.
- `stage4_runtime_model`은 후보별로 같은 공개 posterior bank와 고정 F를 사용한다. F는 공개 커널, 안전 비용 계획의 첫 그룹, Q/UNIT10_SUMMED 순서로 판단한다. F 입력은 공개 정보로 제한된다. 모델의 가상 환경이 표본 배치를 소유하며, terminal reward에서 sampled 3BV를 사용한다.
- F cache는 한 모델 호출 안에서 완료된 불변 결과와 원 request/proof를 보존한다. 실제 입력 permit과 과거 deadline은 cache 대상에서 제외한다.
- `stage4_runtime_policy`는 S/M/R, 공개 count, episode/instance/settings와 quota를 결속한다. 기본 모델 시도 한도는 판당 8회이며, 직전 시도 후 counted 16 경계를 적용한다. 모델 30초, 상위 35초, F fallback 5초를 구분한다. 실제 입력은 output harness의 RuntimePending/R1이 검증한다.
- S는 안전 후보를 우선하고 불가피한 추측에서 정확 최소위험 범위를 사용한다. M은 실패를 0으로 둔 mean X, R은 명시한 target 도달률을 먼저 비교한다. X는 WON의 3BV/C, LOST/GUESS_BLOCKED는 0, 미완료는 null이다. 완전한 candidate×bank 행렬에서만 점수를 발행한다.

원 API의 기본 samples 8, shortlist 4, matrix 32, 모델 30초, 가상 입력 20,000회/row 512회, F lookup 16,000회/miss 4,096회, kernel 60M/Q local 10M/Unit10 30M/cache 2,048개를 유지한다. 작은 전수 witness에는 별도 등록 한도를 썼다. 점수의 범위는 선언된 후보와 고정 F를 사용하는 모델이다. 실제 재계획 정책의 정확한 기대값과 전역 최적성은 미확립이다.

## 원 구현과 독립 검토

기존 호환성 14시험과 신규 23시험을 구분한다. 독립 검토는 커널 proof 388개와 작은 corpus 234결과·1,822배치에서 비건전 0건을 확인했다. 원 probe 857개는 COMPLETE 388개, WORK_LIMIT 455개, DERIVED_LIMIT 14개다.

완료 퇴행 3건은 모두 closure와 publication 뒤 최종 verification에서 500,000을 넘었다. 독립 재생 필요량은 E01의 C82에서 558,754, E01의 C118에서 600,584, V05의 C123에서 504,762다. 같은 형태의 29건도 재생됐다. 검증 비용을 제외한 산술값은 417/857로 목표 686에 미달한다. 이 값은 새 실행 성과로 집계하지 않는다.

원 강제 모델 18회는 COMPLETE 4회, RESOURCE_LIMIT 14회이며, 미완료 사유는 모두 TIME_LIMIT이다. 13건은 kernel 60M 예산을 사실상 소모했다. cache lookup/miss/hit는 각각 16,770/11,220/5,550회다. 실전 hit 비율은 S 1.16%, M 1.56%, R 1.58%다. 서로 다른 work와 시간의 단위를 유지한다.

작은 전수 G009는 S의 OPEN(3,0)에서 2/5, M/R의 CHORD(3,1)에서 1/2다. G001은 12/35, G010은 7/15이며 R target 6/5의 hit는 0이다. 과거 G010 반복 G의 23/60·hit 1/5와 현재 고정 Q/F 직접 모델은 평가 의미가 다르다. 실제 작은 M/R 차이는 NOT_ESTABLISHED다.

## 실전 16회

새 W01–W04에서 기준선/S/M/R을 각각 한 번 실행했다. 배치, 첫 관측, 등록 순서, RNG 복원과 실제 입력 1,520회를 독립 재생했다. 네 역할 모두 0/4승이며 미완료 판은 없다.

| 보드 | 기준선 C | S C | M C | R C | 결과 |
| --- | ---: | ---: | ---: | ---: | --- |
| W01 | 2 | 2 | 2 | 2 | 전부 LOST |
| W02 | 157 | 164 | 164 | 164 | 전부 LOST |
| W03 | 131 | 132 | 132 | 132 | 전부 LOST |
| W04 | 84 | 84 | 84 | 84 | 전부 LOST |

S/M/R의 보드별 원자 수순은 같다. 모델 시도는 mode별 23회이며 S는 선택 2회·fallback 322회, M/R은 선택 0회·fallback 324회다. S 선택 2건은 W03의 C115와 W04의 C82에서 후보 1개×bank 8개를 완료한 경우다. M/R은 같은 공개 상태에서 4후보×8행을 끝내지 못해 공통 F를 사용했다. 이 동일 수순으로 목적함수의 동등성을 주장하지 않는다.

## F1 원 문제와 보완

원 `_row`는 남은 모델 예산에 따라 F의 kernel/Q 한도를 축소했다. 같은 공개 상태에서 F가 다른 행동을 한 원시 사례가 있었으나 F_ID와 COMPLETE 표시는 같았다. P01/S는 F 호출 3,099/3,220회, W04/S 선택은 344/518회에서 kernel 한도가 축소됐다. 이 두 점수는 등록된 고정 F의 값으로 수용되지 않았다. 원 보고의 4/18을 보존하고, 엄격한 등록 F 완료는 P04의 S/M/R인 3/18로 구분한다.

보완 모델 ID는 `RUNTIME_COMMON_POSTERIOR_THEN_PUBLIC_F_V2_FIXED_LIMITS`다. `_row`는 매번 기본 FollowupLimits를 만들며 kernel 500,000, Q local 20,000, Unit10 200,000, F 5초를 유지한다.

캐시 조회와 검증이 miss 예약보다 먼저다. 유효한 완료 hit에는 backend 재실행 예약이 필요 없다. miss는 세 자원 전체와 남은 5초를 확보할 수 있을 때 실행한다. 부족하면 KERNEL_BUDGET/Q_LOCAL_BUDGET/UNIT10_BUDGET/F_TIME_RESERVATION 사유로 모델을 RESOURCE_LIMIT 처리한다. 오류·취소·unknown 회계는 별도 경로로 유지한다. 실제 호출이 생긴 경우에만 호출 인덱스와 소비를 기록한다.

보완 시험은 원 모델 9개와 신규 9개, 고유 18개를 한 번 실행했다. 경계 사례 41건에서 자원·시간 경계, hit와 miss, 캐시 거부, 현재 제약, 실패 회계, 모델 중단, 완료 행렬, runtime fallback을 확인했다. 제어 clock/fake F와 실제 작은 모델을 구분한다.

보충 독립 검토는 V2 모델 API 34개 안의 F 참조 266개가 모두 등록 한도임을 확인했다. 참조는 실제 250개와 주입 16개다. 실제 F API 150개 중 모델 miss 146개가 원시와 결합됐고 lease 합계가 원장과 같았다. witness 9개와 cache-OFF 3개, 합계 12개는 옛 결과와 같았다. 독립 엔진 595 step과 bitmask 52개로 행·보상·점수·선택을 확인했다. 새 필수 문제는 0건이다.

F1 보완 파일의 SHA256은 다음과 같다.

- `stage4_runtime_model.py`는 `552c4370babef3965dbfc6dfcd3214393056c9053a1a922a516961f7ab3e24c9`다.
- `tests/test_stage4_runtime_model.py`는 `24da04520646bee860e1bde067cfc260acdb4cef8ce0c8910d69a730ccce99c5`다.

수정 후 큰 모델은 측정하지 않았다. 따라서 이번 보완에 대한 새 가용성 수치는 없다.

## 실행 이력과 한계

원 실행 START 5/image 10, 보완 추가 1/2, 누적 6/12를 구분한다. 보완의 실제 호출은 모델 34/F 150/Q 45/kernel 149/Unit10 45/Unit4 58이다. 가상 입력은 717회, 실제 engine 입력은 0회다. 실제 소비 kernel 40,966/Q local 1,288/Unit10 7,130/Unit4 4,039/sampler 1,719는 각각 별도 단위다. actual pending/unknown은 0이며 시험용 unknown은 별도로 기록했다.

격리와 종료는 원시 기록 수준에서 확인했다. 보완 Job은 600초이며 TJO 호출 1회, 요청 코드 238로 종료된 구성원 0개, 세 구성원 exit 0, 최종 active/member 0이다. 원 I01/I02와 보완 I01–I03의 실패본을 보존했다. 보완의 출력·읽기·ISO 날짜 자동변환 문제를 고친 과정에서 추가 START는 없었다.

| 항목 | 처분 |
| --- | --- |
| N1 | 커널과 계획기의 proof 검증 중복, 기존 과금과 퇴행 수치를 유지한다. |
| N2 | 원 TIME_LIMIT 뒤의 kernel 예산 소모를 기록한다. 새 F1 gate의 자원 부족 사유와 구분한다. |
| N3/N4 | 같은 요청의 재시도와 episode/instance/settings 수명은 운영 통합 전 계약 대상이다. |
| N5 | 기한은 협력적이다. 원 최대 model 30.0132초와 parent 35초 범위 확인을 유지한다. |
| W1/W2 | 후보 1개 완료와 점수 기반 선택 이득, 공통 fallback 수순과 목적 동등성을 구분한다. |
| S-NB1 | 등록 F 내부 시간 한도를 거친 결과는 cacheable=false다. V2 완료 15개/F 참조 265개에서 해당 사례는 0건이며 후속 관찰 항목이다. |
| S-W1 | 고정 5초에서 hit의 CURRENT_F_DEADLINE 분기는 미도달 코드다. 현재 deadline은 별도로 검사한다. |

원 U1–U5와 보충 S-U1–U4를 보존한다. oracle_masks 비교의 미확인, staged0의 독립 tree 미도출, 실제 risky CHORD 미관측, CPU 미계측, 미노출 설정, 프로세스의 기록 수준 확인, 구현자 시험과 독립 증거의 구분을 유지한다. 조율의 최초 status 공백 처리 오류도 원본과 보정 기록을 보존했다.

## 근거와 다음 경계

근거 root는 `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_PRACTICAL_SMR_UNITS24_26_2026-11-08`이다.

| 묶음 | 자기 제외 manifest |
| --- | --- |
| codex_01 | 862파일 / 2,490,899,869 bytes |
| review_claude_01 | 39파일 / 69,485,222 bytes, SHA256 76e842962c90049fd59e8e56b541c7b0f9d355e6005b361853fdca92c3a282c2 |
| codex_02 | 134파일 / 9,269,568 bytes, SHA256 fb35163c632cf697b191ee6eec5a90327c735bb105d2ecf1ccc548b2f39d0ceb |
| review_claude_02 | 22파일 / 163,124 bytes, SHA256 da37313567fa91fa1c1dad5d73c3f2373a3b1a3b1fcf7da78e8bfb335ea0f660 |

조율 결정은 검토된 실험 코드와 F1 보완의 보존이다. 가용성·실전 선택·효율의 채택 조건은 미충족이다. 다음 단계는 계산 모델과 가용성 기준을 다시 정하는 조율이며, Main/worker/UI/Replay 통합은 보류한다.

Units21–23 MIXED·정책 미채택과 Unit17–20 이력, Stage4 NOT_MERGED, D0–D5 CLOSED, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED를 유지한다. Production K/Gate P와 Phase2/R0-B/ActualE2의 미승인·미실행, frozen 정책·Model C·holdout 2,010,000..2,010,099·금지 formal evidence, F02와 과거 Qt FileDialog/TEMP 한계도 유지한다.
