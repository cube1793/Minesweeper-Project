# Stage 4 Units21–23 공개 추론·안전 비용 API와 제한 비교 마감

## 범위와 조율 판정

2026-11-08에 공개 부분집합 추론, 여러 안전 성분의 정적 비용, 공통 output 정책과 제한 비교를 묶어 검토했다. 순수 API와 신규 시험 네 파일은 검토된 bytes 그대로 실험용 미연결 모듈로 보존한다. 전체 PUBLIC_FACT_COVER_V1 정책의 성과는 **MIXED**, 정책 채택은 **NOT_ADOPTED**다. Stage4 상태는 **NOT_MERGED**다.

| 축 | 조율 처분 |
| --- | --- |
| 공개 추론·비용 순수 API | BOUNDED_ACCEPT, 실험용 API로 보존 |
| output 전달 | LIMITED_ACCEPT, harness 확인 범위 |
| 개발판 | 원 승리 합계 336→328, 등록 기준 통과 |
| 별도 V8 | 승리 4=4, matched-win C 657→666, 등록 기준 실패 |
| 전체 정책 | MIXED, NOT_ADOPTED |
| Main/worker/UI/Replay·일반 효율 | 후속 범위, 전체 수용 미확립 |

제품 필수 수정0, helper/evidence 필수 보완0이다. 신규 네 파일은 기존 Main/Live 동작과 연결하지 않은 상태다. 이번 마감에서 추가 Python·owner·게임·native를 실행하지 않았다. 사용자 native 확인은 UI/실행 통합 단계에서 다룬다.

## 실행 기준과 파일

실제 구현·시험·20회 비교의 HEAD는 `40a7f0edac0725b0d292c8513ed8fca21f6a7bb8`이다. 출발 source365/tracked447, index SHA256 `5fd48aa1c231fe5813b836136bbda4c221082cc48ee872a22f50c159b89084b3`를 보존했다. 새 source4를 더한 source369와 문서6경로를 이번 Git 마감 대상으로 준비한다. 예정 tracked는452다. 이후 마감 commit을 과거 시험 HEAD로 소급하지 않는다.

| 새 파일 | SHA256 |
| --- | --- |
| stage4_public_kernel.py | 5e1b6e5c7837db64c2821ea9a62e15ee6ec9f6c33f1dc6095ff54dcdf7b13a9d |
| stage4_efficiency_plan.py | 6688dd7d5d12f7cf36e2bdf3a8235a598b3a866788df10c51b999677efece0a4 |
| tests/test_stage4_public_kernel.py | 0e59172191d4b0f7ff6578e3e21a478fd5a6f604b2dc13b5038c1a253c15bb50 |
| tests/test_stage4_efficiency_plan.py | 260e1a250ebb12323efb7a7e1fbeac036412cf945165f6de9ebc093ea3be9e54 |

`infer_public(KernelRequest)`는 공개 숫자·총 지뢰 수의 제약, 0/전체 전파, 정규화와 진부분집합 차집합을 적용한다. 물리 FLAG도 미확정 변수다. COMPLETE는 이 규칙 계열의 고정점이며 각 사실은 공개 proof DAG로 결속된다. 한도·취소·오류 결과는 사용 가능한 사실을 비운다.

`plan_safe`는 공개 proof를 검증한 뒤 공유 표적·필요 지뢰 FLAG로 연결된 성분을 비교한다. 새 FLAG, 안전 FLAG 해제, CHORD와 남은 직접 OPEN을 중복 없이 센다. 기본 한도는 커널480칸/제약2048/파생1024/work500000/협력2초, 비용 계획은 성분12 pivot/96표적/부분집합131072/협력1초다. 큰 성분은 UNSUPPORTED_SIZE로 구분한다. 정적 비용은 미래 flood나 새 숫자의 효과를 포함하지 않는다.

output의 PUBLIC_FACT_COVER_V1은 첫 그룹만 예약하고 그룹 종료 후 다시 관측한다. 커널 미완료 또는 안전 진행 부재에 한해 기존 Q/UNIT10_SUMMED를 호출한다. 부모5초와 커널2/cover1/Q2초의 잔여기한을 적용한다. 오류·모순·취소·회계 불명확·기한 만료는 입력을 차단한다. 실제 worker/UI의 세대·수동 인계·Replay 통합은 아직 연결하지 않았다.

## 시험과 독립 확인

신규 시험21개는 kernel8/plan6/output7이며 같은 bytes에서 START21/PASS21이다. 구현자 oracle은38,294 mask와298 BFS 상태다. 독립 검토는 별도13,276 mask로 focused soundness를 확인했다. 두 수량을 합쳐 단일 시험 실적으로 쓰지 않는다.

- 비교20회1,714입력과 저장 Unit18 기준341입력을 독립 엔진으로 재생했다. 총2,055 step이며 before/after·승패·counted·3BV·X 불일치0이다. 별도 MT19937 모델로 등록 seed의 배치를20/20 재현했다.
- COMPLETE339개의81,688 proof node에서 root·규칙·DAG 순서·투영·고정점·request/proof id를 전부 확인했다. 모든 사실과 식은 재생 배치에서도 참이었다.
- plan339개를 독립 재도출했다. READY307/NO_SAFE_PROGRESS32, exact 성분656/큰 성분56이 일치했다. exact656은 독립 부분집합 원자 시뮬레이션으로 확인했고482개는 원자 BFS로도 확인했다. 나머지174개는 BFS 미검사로 남겼다.
- 공개 kernel 그룹307개는 첫 그룹만 예약했고, 그룹 도중 Q 호출0이다. proof·관측·count·generation 결속과 입력별 guard를 확인했다. 공개 kernel 입력에서 패배한 판은0이며 이번20회 확인 범위에 한정한다.

## 제한 성과

| 판 | 기준 C | 후보 C | 결과 |
| --- | ---: | ---: | --- |
| E01 | 163 | 162 | 양쪽 WON |
| E02 | 173 | 166 | 양쪽 WON |
| E03 | 3 | 3 | 양쪽 LOST |
| E04 | 2 | 2 | 양쪽 LOST |
| V01 | 187 | 188 | 양쪽 WON |
| V04 | 138 | 140 | 양쪽 WON |
| V05 | 168 | 170 | 양쪽 WON |
| V08 | 164 | 168 | 양쪽 WON |

V02/V03/V06/V07은 양쪽 LOST, C8/2/9/10이며 수순 전체가 같다. 개발4판의 기준선은 저장 근거를 재사용했고 후보만 새로 실행했다. V8은 새8배치에서 기준선/후보를 각각1회 실행한16회다. 교체·재경기는0이며 개발판과 검증판을 분리한다.

V8 합계 X는 기준 `120681455/29625288`, 후보 `2696059/671160`으로 감소했다. X는 WON시3BV/C, LOST0이다. 미완료 판은 없었다. 개발 승리 합계336→328과 V8 실패를 합쳐 **MIXED**로 판정한다. 표본8의 일반 우위나 통계적 유의성은 확립하지 않았다.

후보12판의 kernel857회는 COMPLETE339/WORK_LIMIT482/DERIVED_LIMIT36이다. 미완료518회는 사실을 비웠고 Q로 넘어갔다. Q fallback550은 이518회와 NO_SAFE_PROGRESS32회다. 후보 입력1,028회는 kernel 그룹378/Q638/첫 OPEN12다. 기준선 runtime_summary의 `fallbacks=544`는 별도 계수다.

양의 exact cover 선택은 E02/V04/V08 각1회이며 정적1입력 이득이다. 해당 전판 C 변화는 -7/+2/+4다. 정적 이득을 실제 절약3회나 인과 효과로 합산하지 않는다. 구현자의 추가 사실233요청·안전771/지뢰516 출현·그룹55 분석은 사후 별도 분석이고 독립 재계산하지 않았다.

## 실패·실행·비차단 처분

I01은 빈 배열의 JSON null 처리로 controller/Python 생성 전에 실패했다. 실제 Python0, 보수 START1/image2를 차감했다. 이후 실제2 START/image4, 전체 보수 START3/4·image6/8이다. 두 실제 Job은 host4 fresh hash, suspended→Job→resume1→graph→release→import, 종료요청0, final active/member0와 handle/pipe 정리를 기록했다. 독립 검토는 과거 원시를 대조했고 실시간 OS 조회는 하지 않았다.

I02의 판 단위 보정 시간에는 run-level Journal 직렬화/fsync 일부가 들어 있다. 순수 연산 시간·속도 향상으로 사용하지 않는다. I03은 PowerShell R 별칭 충돌이며 원 실패 전체 stdout은 미보존이다. 구현자 helper 보정1/3, 읽기 보정1/4, incident3/8을 유지한다.

| 항목 | 처분 |
| --- | --- |
| NB1 | cover 잔여기한의 0 하한 clamp 부재. 발생 시 입력 없이 구조 중단하며 원시 미발생이다. 통합 전 robustness 후속으로 남긴다. |
| NB2 | WORK_LIMIT482/857, 최소6회는 publication 선과금에서 중단했다. 추론·검증·발행 예산 개선은 별도 등록하고 원 한도를 변경하지 않는다. |
| NB3/W1 | OuterContainment.cs·RecordedOwnerRead.psm1은 byte 동일이다. controller/driver/protection/invoke는 hash 등록된 배선 수정본이며 diff 문서 부재를 남긴다. |
| NB4 | 기준선 fallbacks544와 후보 Q fallback550을 구분한다. |
| NB5 | 비교에서 잔여기한 분기가 작동하지 않았다. source/focused 확인 범위를 유지한다. |
| NB6 | 정적 cover와 전판 C는 다른 지표이며 인과 효과를 주장하지 않는다. |
| W2 | 조율 초기 미검토 항목 중 엔진·proof·plan은 이번 독립 검토로 확인했다. 당시 조율 기록 자체는 보존한다. |

U1~U10도 유지한다. 사후 FACT_DELTAS, BFS174개, focused 큰5행의 bitmask, 실시간 OS, ledger digest, family별 work·한도 단계, Q 내부 정합성, 이전315 member 및 Git 읽기 조건, 완전성, 미노출 설정은 각 검토 범위를 넘는다. 커널은 focused oracle의 강제 안전99/지뢰120 중97/118을 찾았으며 완전성 요구는 없다.

검토 도구 보정2/3, 읽기0/2, incident1/5를 기록했다. harness가29.1MB stdout을 세션 tool-results에 자동 저장한 예외를 포함한다. 제품·repo·Git·Desktop·memory 쓰기와 제품 실행은0이다. Fast OFF는 요청값과 실제 확인을 구분하며 FINDINGS의 UNCONFIRMED를 따른다.

## 근거와 후속

근거 root는 `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_PRACTICAL_CORE_UNITS21_23_2026-11-08`이다. 구현 `codex_01` manifest는508파일/78,331,411 bytes다. 독립 `review_claude_01` manifest는31파일/32,194,161 bytes, SHA256 `ca6b3a7a006a316723b49780bb182c82822f3a12c554b2e4c5467a3e00b1cba2`다. 보고서·FINDINGS·CROSSCHECK·원장과 조율 `coordinator_01/02`의 원본을 보존한다.

다음 범위는 이 API를 활용할 S/M/R 선택·실전 평가·worker/UI 연결이다. 커널의 예산 소모와 정적 이득의 일반화 문제를 고려해 범위를 다시 등록한다. 이번 마감만으로 후속 실행을 시작하지 않는다.

Unit17 MIXED/PARTIAL, Unit18 제한1클릭/UNKNOWN/PARTIAL, Unit19 MIXED·통제 R1, Unit20 NO_IMPROVEMENT, 원 실패를 유지한다. D0–D5 CLOSED, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED, Production K/Gate P·Phase2/R0-B/ActualE2 미승인/미실행, frozen 정책·Model C·holdout2,010,000..2,010,099·금지 formal evidence 경계도 유지한다.
