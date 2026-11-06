# Stage 4 Unit 9 — 보존 후보의 검증과 미채택

기준일: 2026-11-07 (Asia/Seoul). 정확 계수·READY 캐시 후보의 수학과 등록된 실측 근거는 독립 재현됐다. 그러나 확대 예산의 채택 기준을 충족하지 못해 **PARTIAL_IMPROVEMENT와 원복이 정당하다**는 판정이다. 후보는 현재 제품에 적용돼 있지 않다. **effectiveness NOT_ESTABLISHED**와 전체 Stage 4 미완료를 유지한다.

## 1. 판정과 현재 소스

| 축 | 독립 판정 |
|---|---|
| 후보 코드 수학 | CORRECT_BOUNDED, 발견된 결함 0 |
| 실측·주장 범위 | REPRODUCED, 원시 없는 일부 소계는 별도 표시 |
| 새 helper·실행·보호 | 새 Job 12개 수용. 원 P01 신원 공백은 유지 |
| 채택·원복 | PARTIAL_IMPROVEMENT / 원복 정당 |
| 필수 / 선택 / 미확인 / 정보 | 제품 0·근거 0 / 11 / 5 / 3 |

출발 HEAD와 local origin/main은 `dfa338d59bf2c2dfc2f5101c54fb36a4732fa91d`, index SHA256은 `ab64e41a3a4d26790abe1553a2d47704045c02bf946549d8fcab44c1a779db40`다. source 362개와 tracked 438개의 기준 bytes로 돌아왔고, 이 마감은 문서 6경로만 추가·수정한다. 실제 사용자 commit/push·recovery receipt와 현재 Git이 이 준비 시점 문구보다 우선한다.

후보 변경은 기존 `stage4_exact_pilot.py`, `stage4_objective_pilot.py`의 연결 지점과 신규 `stage4_belief_accel.py`, `stage4_exact_accel.py`, 시험/참조 3파일의 총 7경로였다. 신규 5파일은 현재 저장소에 없다. 현재 Q/G는 Unit 8의 기준 구현이며, 후보 실행 snapshot과 구분한다. 독립 검토는 patch를 메모리에서 적용해 7파일 모두 실행 snapshot과 같음을 확인했다.

## 2. 후보가 확인한 것

정확 계수 후보는 events=0 base 전용이다. 잔여 제약의 강제 배정·정규화·결정적 분기·메모와 lift로 D 및 모든 칸 M을 정확한 정수로 계산한다. 실제 배치나 미래 관측을 정책 정보로 쓰지 않는다. 기존 Unit 4의 수학적 request identity와 후보 backend version은 별도로 결속했다.

READY 캐시는 G 요청마다 생성·폐기하며 물리 FLAG, 총 지뢰 수, C, guess, prior와 구현 version을 key에 포함한다. 기존 base cache 256개와 새 READY FIFO 최대 4,096개/직렬화 payload 32 MiB는 서로 다르다. hit 전후에 현재 시간·취소·지원·재귀·0한도를 검사하며 현재 request_id와 과거 계산 origin을 분리한다. 부분·실패 결과는 저장하지 않는다.

신규 18개와 기존 Q 15/G 14 회귀의 **이번 run03 47개 시험**이 통과했다. 과거 Unit 8의 29개 실행과 합쳐 새 단일 실행이라고 쓰지 않는다. 독립 검토는 별도로 무작위 소형 관측 364개(일관 310/불일치 54)를 194,080 bitmask로 확인해 불일치 0이었다.

| hard 공개 상태 | reference 3회 | 후보 3회 | 독립 D / M |
|---|---|---|---|
| a14e1857, 큰 component 111칸 | 매번 200,000 work cap | 매번 정확 완료 | D=978,313,118,206,356, M 179칸 일치 |
| 0e08c76d, 큰 component 109칸 | 매번 200,000 work cap | 매번 정확 완료 | D=7,941,240, M 142칸 일치 |

새로 작성한 독립 계수기는 후보나 과거 Unit 4 counter와 다른 알고리즘이다. 각 상태의 ΣM=N×D도 성립했다. 후보 회계를 따라 별도로 만든 mirror는 work 1,104/811, auxiliary 25,021/22,695, 메모와 checkpoint를 재현했다. work 분해는 강제/분기/DP가 336/170/598 및 321/106/384다.

**1,104 대 200,000을 계산량 또는 속도의 단순 배율로 해석하지 않는다.** 후보는 제약·메모·histogram 작업을 별도 auxiliary로 계수하며 G의 exact/local 합계 예산에 넣지 않았다. 공통 실자원 제약은 2초 Q/30초 G이고, 명목 work cap과 실제 작업의 의미를 구분한다(U9R-O01).

B의 현재 int `2`와 과거 float `2.0`은 같은 시간 한도지만 서로 다른 request_id를 만든다. 독립 검토가 두 ID를 모두 재현했다. 현재 두 구현의 비교에는 같은 요청을 사용했으며, 과거 identity와 같다고 주장하지 않는다.

## 3. 완료율과 재생

| G 예산 | 새 reference | combined | 기존 완료 회귀 |
|---|---:|---:|---:|
| 기본 exact20M/local10M, 30초 | 0/18 | 3/18 | 0 |
| 확대 exact60M/local30M, 30초 | 3/18 | 3/18 | 0 |

18은 같은 Replay의 6개 공개 시점×S/M/R이다. 각 G의 표본 N16/후보 K6, Q exact 200,000/local 20,000/최대 2초, G Q호출 5,000회를 유지했다. “같은 예산”은 **같은 시간 및 명목 한도**라는 뜻이며 auxiliary까지 동일하게 과금한 총 계산량 비교는 아니다.

기본에서 새로 완료된 3요청은 snapshot_128 S/M/R이다. 확대 최소 6/18, baseline보다 3요청 증가, 새 공개 시점 1개 증가라는 동결 조건은 모두 미충족이다. E의 확인 반복은 조건에 따라 **NOT_TRIGGERED, 0회**였다. 결과를 본 뒤 조건을 완화하지 않았다.

C의 72 G/36 pair는 root/bank/shortlist와 겹치는 완료 행 1,736개, 부분 prefix 33개가 일치했다. 확대 combined의 미완료 15건은 **Q_CALL_LIMIT 5,000회 10건, G TIME_LIMIT 30초 5건**이다. 현 계약에 따른 중단이며 현재 제품 결함 판정이 아니다.

D는 고정 확대 6개 S 요청에서 memo-only/counter-only를 각각 실행했다. 양쪽 모두 snapshot_128_S 하나, 즉 1/6만 완료했다. 단독 정확 계수 해결과 전체 G 완료율을 구분한다.

독립 검토는 새 완료 3요청의 288행·Q 7,971회·점수·선택과 나머지 완료 G 8개까지, **완료 C/D G 11개 전체 1,056행**을 독립 엔진/Q로 재생했다. 해당 범위의 READY hit 4,516회는 새 계산과 일치했다. 전체 hit 47,325회 모두를 재계산한 것은 아니다. F의 모든 Q도 별도 확인됐고, 나머지는 불변식으로만 확인됐다.

F는 24 trial, 13 WON/11 LOST, G 48회, 94입력(prefix 42+정책 52)이다. G는 직전 macro를 모두 적용한 뒤 호출됐다. **각 원자 입력마다 G를 다시 부른 실행이 아니다.** G009 S 2/5·M 1/2, G001 M/R 12/35, G010 M 7/15·R 23/60을 재현했다. 후보 뒤 Q 모델과 이 반복 G 실행, 일반 상급판 성과를 구분한다.

## 4. 실행·계측·보호

원 codex_01은 P01에서 conhost를 허용 판정 전에 기록하지 못해 **PARTIAL_P01_CONTAINMENT_STOP**으로 남았다. Job total 2/완전 신원 1의 과거 공백은 복구되지 않았다. 해당 91파일과 manifest는 그대로다.

codex_02의 새 helper는 발견한 PID·신원·핸들을 허용 판정 전에 보존하고, 전체 snapshot 후 부모 관계를 검사한다. conhost는 시스템 경로/hash·자기 Job·생성시각으로 확인한다. 새 run01은 user code 전 exit 101이지만 2멤버의 신원·정리는 확인됐다. 새 run02의 3멤버 gate(21:38:47Z) 뒤 제품 run03(21:42:11Z)을 시작했다. exit 101의 OS 원인은 미확인이다.

새 Job 12개의 신원·정리를 독립 수용했다. 새 Python 23개와 원 실행의 보수적 charge 2를 더해 **Python charge 25/40**, 논리 시작은 원 1+새 12=13/20이다. 새 관측 Job member는 35개다. 이미지 기반 근거와 owner 0이라는 원장 진술의 독립 확인 한계는 구분한다.

run07은 종료 단계에서 active conhost 1개를 관측하고 TJO를 호출했다. 최종 모든 멤버 exit는 0이며 실제 종료된 멤버는 없다는 독립 판단이다. TJO 요청 자체가 0이었다고 쓰지 않는다(U9R-O04).

원시 집계는 G 167, timed Q 286,472+중첩 guard 1=총 Q 시도 286,473, backend 32,050, slot 1,590, 시작 model행 6,092, 가상 입력 340,820, exact 87,638,786, local 886,454,368, auxiliary 108,165,269다. 중첩 Q 1회는 통과한 assert 근거이며 별도 timing 행이 없다. nested G 거절 2회는 A의 G 35회에 포함된다.

C combined hit는 41,607, 모든 phase hit는 47,325다. 최대 READY entry 3,685, payload 11,785,573 bytes를 기록했다. 혼합 profile 배치의 표본 peak private 511,008,768/RSS 528,424,960 bytes와 OS Job peak committed 511,008,768 bytes를 구분한다. 실제 Job memory limit는 1,610,612,736 bytes다. profile별 메모리 우위나 payload의 실제 메모리 보장으로 확대하지 않는다.

사용자 보충에 따라 `max_G_calls_per_batch=12`는 C/D/E 성능 비교 batch에 적용했다. A/F 내부 G도 전체 500회와 시간·메모리 예산에 포함했다. 문구 모호함과 보충 시점, A 35회 이미 포함 및 재시험 0을 보존한다.

## 5. 선택 발견 11건 — 원본 수정 없이 처분

| ID | 마감 해석 또는 남은 설계 메모 |
|---|---|
| U9R-O01 | auxiliary는 G exact/local에 미과금. 동일 시간·명목 cap으로만 기술. 향후 총 auxiliary 예산 또는 병기 기준을 먼저 정할 것 |
| U9R-O02 | 공개 cache_entries는 base cache만 제어하며 READY는 별도 4,096. 재사용 시 분리 한도를 명시하거나 노출할 것 |
| U9R-O03 | READY miss로 삽입한 117,189건에도 execution.origin이 있다. hit 판별은 origin 유무가 아니라 ready_cache_hit |
| U9R-O04 | run07 TJO 호출을 문서화. 모든 exit 0, 실제 종료 멤버 0. 재실행 불필요 |
| U9R-O05 | standalone count_base의 0한도/unsupported 우선순위가 reference와 다름. 현재 Q 경로에서는 선행 검사로 도달하지 않음 |
| U9R-O06 | oracle_masks 21,212 = 원시 재구성 21,184 + 이전 oracle의 원시 없는 28. 28은 NOT_INDEPENDENTLY_RECOUNTED |
| U9R-O07 | 상태 없는 choose_exact는 매번 새 READY 캐시에 삽입·직렬화하고 버림. 재사용 시 해당 진입점의 불필요한 삽입을 검토 |
| U9R-O08 | execution.serialization_nanoseconds는 Q 안의 cache payload 직렬화. driver serialization_ns는 timed 구간 밖 원시 dump/gzip/쓰기. 서로 다른 항목 |
| U9R-O09 | Python은 path/계보/Job/시각 검증이며 image_sha256=null, conhost만 hash 검증. 선택적 강화 메모 |
| U9R-O10 | A_raw의 context는 단일 시험 이름이나 실제 내용은 run03 47시험 전체 집계. 파일명/context로 범위를 축소해 해석하지 않음 |
| U9R-O11 | 정확 계수만 별도 단위로 재사용을 검토할 근거가 있음. 합산 과금/독립 등록/별도 비교가 필요하며 결합 후보 채택이 아님 |

원 산출물은 바꾸지 않고 위 문서와 조율 처분에서 해석을 바로잡았다. 선택 11건을 전부 FIXED/CLOSED로 바꾸지 않는다. 필수 발견은 제품/근거 모두 0이다.

## 6. 독립 검토 범위와 남은 한계

- U9R-U01: 구현자 큰 참조 work 1,576,099 중 hard 1,457,792는 과거 counter 사본으로 재현했다. 나머지 118,307은 그 도구 단위로 독립 재계수하지 않았다.
- U9R-U02: 완료 C/D G의 4,516 hit 및 F 범위 밖 hit는 원시 불변식만 확인했다. 전체 hit 재계산이라고 쓰지 않는다.
- U9R-U03: 미완료 C 63개·D 10개의 부분 행은 독립 엔진 재생하지 않았다. pair prefix/overlap과 회계를 대조했다.
- U9R-U04: exit 101과 sandbox 밖 retry 성공으로 OS 원인을 확정하지 않는다.
- U9R-U05: owner/Qt/CUA 0은 이미지·assert·원장으로 지지되지만 owner 부재 자체를 독립 관측한 것은 아니다.

구현자의 자체 검증은 과거 Claude counter/lib8 사본을 사용했다. 이번 독립 검토의 1차 근거는 새 fdp/engine/mirror 구현이며, 두 종류의 검증을 구분한다. 검토자는 약 40분, bitmask 194,080/200,000, 전이 37,469/100,000, 기록된 계수 work 약 13.9M/200M을 사용했다. 명령 보정 2/2와 과대 출력 재발·BigInt 직렬화 오류를 원시에 보존했다.

## 7. 다음 범위와 영구 경계

다음 후보는 정확 계수 부분을 분리해 재사용할 수 있는지 검토하는 것이다. 먼저 **auxiliary의 총예산·작업 단위, READY와 base cache 한도, 단독 진입점의 불필요한 직렬화**를 계약으로 정한다. Q 5,000회/30초를 단순히 높여 기존 채택 기준을 소급 충족시키지 않는다. 논리 호출 수와 실제 작업량, 모델 끝까지 진행 비용을 구분한다.

현재 제품 코드는 Unit 8 상태로 유지한다. UI/Live·전시 노트북·패키지·일반 효율 평가, Stage 3 50/50·오프닝·색 갱신, 저장 자료 삭제/정리는 자동 시작하지 않는다. 제품 변경이 없어 이번 문서 마감에 추가 native는 필요하지 않다.

원 Unit 8 PARTIAL/H05/원 manifest 부재, 원 Unit 9 P01 신원 공백, 과거 C01/H01/U3-H01/U6-R02/U7-R01을 유지한다. D0–D5 CLOSED, V1 FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT_ESTABLISHED, Production K/Gate P 미승인, Phase2/R0-B/ActualE2 미승인, frozen 정책·Model C·holdout 2,010,000..2,010,099·금지 formal evidence는 변하지 않았다.

## 8. 근거 위치

root: `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_EXACT_COMPLETION_UNIT9_2026-11-07`.

- codex_01: 91파일/1,237,871 bytes, manifest SHA256 `72e9b98edc751066ef7677d14111b7c46e373671bf80a4750bd02494d8a5cd52`.
- codex_02: 526파일/158,550,137 bytes, manifest SHA256 `6c9825ce0488a50f4c47a12590f4d4936b0f84e968c84d6cc8f6199a87568404`.
- 보존 후보: `codex_02/source_versions/v01` 및 `CANDIDATE_PATCH.patch`; 현재 repo에 적용하지 않음.
- review_claude_01: 41파일/811,696 bytes, manifest SHA256 `5077ab00d1b81d9388263c02984d77365e85480d5359e3f4aa8fda91fdd22d32`.
- 조율 문서/Git 준비: `outputs/STAGE4_UNIT9_CLOSEOUT_2026-11-07/coordinator_01`.

검토 실행의 실제 모델/설정과 구현자의 미노출 설정은 각 원장 범위대로 읽고, 확인되지 않은 값을 추정해서 확정하지 않는다.
