# Stage 4 Unit27 고정 F 프로파일 비교 마감

## 현재 판정

등록된 54개 모델 호출을 모두 한 번씩 처분했다. 실행과 정확 산술은 독립 검토에서 확인됐으며 필수 제품 보완과 필수 helper 보완은 각각 0건이다. 세 프로파일 모두 **AVAILABILITY_NOT_MET / MODEL_INFORMATION_NOT_OBSERVED**, 후속 프로파일은 **NONE**이다. source와 기본값은 바꾸지 않았다. **INTEGRATION_NOT_READY / 효과성 NOT_ESTABLISHED / Stage4 NOT_MERGED**를 유지한다.

이 단위의 실행 HEAD는 `03d26861f3544cb5c20495f42f3414b448f3cf6e`다. 현재 source 375개와 출발 tracked 459개를 보존했다. 이번 마감은 문서 6경로만 대상으로 하며 예정 tracked는 460개다. 이후 commit을 과거 시험·측정 HEAD로 소급하지 않는다.

## 등록 범위와 결과

기존 `evaluate_model`에서 samples/shortlist/rows만 바꿨다. P01–P06의 공개 관측, S/M/R, 프로파일 세 개를 조합했다. 각 P의 공개 planning seed는 같으며 R의 진단 target은 정확한 6/5다. 6/5는 추천 설정이 아니다. 실제 게임·정책 owner·UI 실행은 0회다.

| 프로파일 | 표본×최대 후보 | rows 한도 | COMPLETE | S/M/R 완료 | S/M/R nonzero | M/R 엄격 차이 |
| --- | --- | ---: | ---: | --- | --- | --- |
| B0 | 8×4 | 32 | 3/18 | 1/1/1 | 0/0/0 | 0/0 |
| P1 | 8×2 | 16 | 6/18 | 2/2/2 | 1/1/1 | 1/0 |
| P2 | 4×2 | 8 | 9/18 | 3/3/3 | 2/2/2 | 2/0 |

등록 기준은 COMPLETE 12/18 이상, 각 mode에서 nonzero 완료 1건 이상이다. 모델 정보 조건은 M과 R 각각에서 복수 후보의 엄격한 주 목적값 차이가 적어도 1건 있어야 한다. 세 프로파일 모두 조건을 충족하지 못했다. M의 주 목적은 mean X, R의 주 목적은 hit rate다. R의 mean tie-break는 엄격한 hit 차이와 구분했다.

B0의 완료 3건은 P04의 S/M/R이며 모두 0점이다. P2의 완료 9건은 P02/P04/P06의 세 mode다. P01/P03/P05의 27개 호출은 프로파일과 관계없이 두 번째 row를 끝내지 못했다. 폭 축소만으로 이 여섯 상태에서 12/18에 도달할 근거는 얻지 못했다.

terminal 447행은 WON 229, LOST 218이며 hit는 모두 0이다. 최대 X는 9/8로 등록 target 6/5보다 작다. 이 범위의 R 차이 부재를 R 알고리즘 불가능이나 제품 결함으로 해석하지 않는다. target을 사후 변경하지 않았다.

## 독립 검토와 결속

검토자는 제품·시험·helper·Git·새 측정을 실행하지 않고 자체 Node 도구를 사용했다. 54개 압축 원시의 필드·배열·끝 기록과 압축/해제 hash, 등록 순서, 호출 간 비중첩을 확인했다. 56개 주장값의 불일치는 0이었다.

- score 42개를 정확한 유리수로 재계산했다.
- 시작된 483행 전체를 독립 엔진으로 재생했다. 전이 15,237회에서 C·승패·3BV·X·hit 불일치가 0이었다. COMPLETE 모델 안의 terminal 264행과 전체 terminal 447행을 구분한다.
- F 기록 12,538개는 miss 11,341개와 hit 1,197개다. gate에서 거절된 lookup 36개는 이 기록에 포함되지 않는다. F의 등록 한도와 miss 전량 예약을 확인했다.
- hit는 같은 logical key의 앞선 miss 결과와 bytes가 같았다. P2의 bank는 각 P의 8표본 bank 앞 4개였고, shortlist 2개는 4개 shortlist 앞 두 후보였다.
- 두 프로파일이 함께 COMPLETE인 비교는 B0/P1 3개, B0/P2 3개, P1/P2 6개다. 해당 선택·순위와 공통 행 48/24/48개가 일치했다. 작은 분모의 일치이며 정확성·효율의 일반 증거로 확대하지 않는다.

고정 F의 kernel 500,000/Q local 20,000/Unit10 200,000/5초와 F1 전량 예약을 유지했다. F 내부 시간 한도 경유는 0건이다. 모델 수준 시간 예약 gate의 중단 1건은 별도로 존재한다.

## 계산 비용과 다음 설계 근거

미완료 36건은 KERNEL_BUDGET 35건과 F_TIME_RESERVATION 1건이다. 후자는 U27-46-P06-S-B0에서 경과 25.063초에 발생했다. 그 호출이 완료됐더라도 B0는 최대 4/18이다.

| kernel miss 결과 | 호출 수 |
| --- | ---: |
| COMPLETE | 7,608 |
| WORK_LIMIT | 3,398 |
| DERIVED_LIMIT | 335 |
| 합계 | 11,341 |

kernel work 합계는 2,355,138,742다. 이 중 1,838,354,270, 약 78.1%가 미완료 kernel에 쓰였다. 미완료 3,733개는 모두 Q로 넘어갔다. miss 기준 EXACT_Q 반환은 3,989개이며, hit를 포함하면 4,562개다.

계획기의 proof verification 120,230,260과 planning visits 37,480,038은 miss의 plan 7,608회에서만 집계했다. 두 계열은 수치 model budget 밖의 별도 단위이며 kernel work와 합치지 않는다. 기록된 총 evaluate 시간 505.033초와 직렬화·I/O를 분리한다. 프로파일별 시간 차이를 최적화 배율로 주장하지 않는다.

다음 조율은 F의 kernel 선행 비용을 대상으로 한다. 고정 한도를 명시적으로 바꾸는 별도 F나 회계가 있는 사전 분류를 검토할 수 있다. 새 F_ID, cache 경계, 전량 예약과 정산이 필요하다. 기존 F를 남은 모델 예산에 따라 축소하는 방식은 F1 재발에 해당한다.

비용 감소와 행동 보존은 별개다. 원시에서 kernel work 100,000을 넘기고 COMPLETE인 호출은 1,272개였다. 한도를 낮추면 이들이 Q로 넘어가 행동·C·X가 달라질 수 있다. 새 설계의 효과는 별도 비교로 확인해야 한다.

## 실행·실패 기록과 비차단 처분

P0 1회, A 1회, B 3회로 START 5/6, Python image 10/12를 사용했다. 모델 재실행은 0회다. 소유 Job은 원시 기록에서 최종 active/member 0과 exit 0을 확인했다. run03의 TJO 요청은 active 0에서 발생해 종료된 구성원이 0개였다.

U27-R01의 표시 잘림 4회, H01의 종료 후 집계 오류, H02의 manifest 사전 속성 묶음 오류를 보존했다. 읽기 보정 1건, helper 보정 2건, 고유 원인 3개, 원시 오류 6개다. H01의 phase_error.json은 집계 v1 사본이며 중복 rank 표시 306→21을 보정했다. B3 Python 실패로 집계하지 않는다. 동결 REGISTRATION과 사후 CLOSEOUT_OUTPUT_REGISTRATION을 구분한다.

| 항목 | 마감 처분 |
| --- | --- |
| RV27-NB01 | cache_peak 합 4,737/3,867/2,737과 호출당 최대 750/434/243을 구분한다. |
| RV27-NB02 | F 내부 시간 경로 0건과 모델 시간 예약 중단 1건을 구분한다. |
| RV27-NB03 | F miss/hit 영수증 12,538개와 거절된 lookup 36개를 구분한다. |
| RV27-NB04 | phase_error.json의 실제 내용은 반환 후 집계 사본이다. 원본 파일명은 보존한다. |
| RV27-NB05 | TJO 요청과 실제 종료를 구분한다. 세 member는 exit 0이었다. |
| RV27-NB06 | terminal 전체 hit 0과 최대 X 9/8을 명시하고 R 불가능으로 확대하지 않는다. |
| RV27-NB07 | P01/P03/P05는 모든 프로파일에서 두 번째 row 미완료였음을 유지한다. |
| RV27-NB08 | total_worlds의 JSON 숫자·문자열 혼재와 정확한 값의 일치를 함께 기록한다. |

RV27-U01–U09를 보존한다. HEAD tree와 staged0의 독립 대조, 난수·unrank 재계산, kernel/plan/Q proof와 root 후보값, miss별 남은 시간, 실시간 프로세스, root 관련 ledger 합계, 미노출 설정, 이전 검토 재독, 저장 timing의 검증 범위를 구분한다. 조율의 현재 Git 확인으로 검토자가 실행하지 않은 항목을 소급 해소하지 않는다.

검토자의 RV27-T01은 index 0을 누락으로 처리한 자체 도구 오류다. v1과 오탐 81건을 보존하고 v2에서 보정했다. 검토 제품 실행 0회, 자체 도구 보정 1/3, incident 1/5를 기록했다.

## 근거와 유지 경계

근거 root는 `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_FIXED_F_PROFILE_PILOT_UNIT27_2026-11-08`이다. 구현 manifest는 501파일/38,870,856 bytes, 독립 검토 manifest는 29파일/1,102,198 bytes다. 검토 manifest SHA256은 `3c5659e550985398cf6e0b9beff0d21389625360580d58f0afdb8808d953b928`이다.

이전 F1_FIXED_BOUNDED와 원 4/18·엄격 3/18, 커널 388/857·퇴행 3, 실전 16패를 보존한다. Unit27은 새로운 공개 planning seed로 측정한 별도 범위다. 일반 효율, 실제 세 목적의 차이, 운영 통합은 미확립이다. D0–D5 CLOSED, V1 FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, Production K/Gate P·Phase2/R0-B/ActualE2 미승인·미실행, frozen Model C·holdout·금지 formal evidence와 과거 F02/Qt/TEMP 한계를 유지한다.
