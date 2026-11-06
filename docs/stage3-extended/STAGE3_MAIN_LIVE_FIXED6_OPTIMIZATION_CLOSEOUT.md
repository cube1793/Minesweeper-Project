# Main/Live 고정 6 CPS 최적화와 사용자 확인

기준일: **2026-11-06 (Asia/Seoul)**. 결합 후보의 측정 근거는 **ACCEPT_BOUNDED**, source는 **ACCEPT / 제품 필수 수정 0**이다. helper H1을 보완하고 검토된 네 파일을 그대로 반영했다. 사용자는 이번 PC의 native 안내에 **“좋아, 모두 통과야.”**라고 수용했다. **전시 노트북 확인은 PENDING**이며 문서·Git·Desktop 마감은 준비 중이다.

이 결과는 현재 기계·보드·세션 및 확인한 기능에 한정한다. 안정 CPS 상한, 모든 부하의 처리량, 효과성, Production 승인 또는 Stage4 전환을 뜻하지 않는다.

## 1. 현재 source와 실행 authority

문서 준비 시 HEAD = local origin/main = `dc711a7917edf3f00bbad26f710b5240c08d7f13`, main, staged 0, ahead/behind 0/0이다. 현재 source 335는 `MAIN_LIVE_NATIVE_FIXED6_OPTIMIZATION_2026-11-06/codex_02/SOURCE_COMBINED.json`과 같다. 테스트·측정은 각 당시 source/helper 서명에 결속하며 이후 commit으로 소급하지 않는다.

정확히 반영한 후보:

| 경로 | SHA256 |
| --- | --- |
| `ui_manager.py` | `93fccf759c51d1c2d07e491364121bef7a8eef0bea470063d58101b38aed2633` |
| `live_policy_job.py` | `91201c0fcfdf740de1b32145f9040536131a6da135d4ad49aab2f12b51b6e9f4` |
| `live_policy_transport.py` | `51acdcc57a770262fff2bf8b72da9f1c6ffd8425eeb9f492dfdeeb7eb383be47` |
| `tests/test_live_policy_job.py` | `805aef704b97313c56b33b26e7e76482b5cfae3817e8acc9b6380007b87eed69` |

CRLF를 포함한 snapshot bytes 복사로 반영했다. 나머지 331 source와 거리 모드·거리 테스트는 그대로다. 이전 거리 기능을 합친 이번 Git 범위는 source/tests 6개와 문서 7개, 총 13경로다. 실제 commit/push·회복 문서의 authority는 이후 사용자 receipt와 destination 검증이다.

## 2. 문제와 최적화

사용자 원본 `replay_20261106_121528.json`은 158입력 / 28.8714136초, Counters 5.472541 CPS였다. 첫·마지막 Replay 이벤트 사이 157 gap은 5.439733 CPS다. 평균 183.833 ms, 최대 236.772 ms로 작은 지연이 누적됐다. 이 사후 이벤트 시각만으로 단독 병목이나 입력 deadline 위반을 판정하지 않았다. 잘못 설정했던 별도 Model C 6배속 판은 비교에서 제외했다.

C1은 `_render_cell`에서 실제 widget 스타일시트 문자열과 목표가 같으면 setter를 생략한다. 기존 font/text·상태별 스타일·외부 스타일 복구는 유지한다. C2는 private 채널의 기대 worker 응답이 게시됐다는 디렉터리 알림에서 기존 `poll()`을 부른다. 25ms fallback, 원 deadline, strict JSON/seq/nonce/token/snapshot/ACK 검증과 정확 ACK 뒤 NEXT는 유지한다. 알림 자체는 입력 승인이 아니다. watcher는 채널 삭제 전에 해제한다.

원 정책 선택·추론·Model C 비용·관람 곡선·fixed cadence와 compute30/ACK5/exit5/drain0.75초 cap은 바꾸지 않았다. 새 알고리즘이나 원 Model C 재적합은 하지 않았다.

## 3. 별도로 보존하는 두 비교

| 단위 | 비교와 결과 | 당시 판정 |
| --- | --- | --- |
| `codex_01` C1 | 원본 대비 3쌍, gap 개선 중앙값 8.796620%, CPU/입력 감소. 후보 5.430/5.533/5.490 CPS | 목표 미달, 미채택 유지 |
| `codex_01` C2 | C1 대비 알림의 추가 효과 4.820778% < 5%, CPU/입력 +13.17% | 증분 FAIL·미채택 유지 |
| `codex_02` S02 | 원본 대비 같은 C1+C2 결합본의 새 직접 3쌍 | 아래 사전 기준 충족, 독립 한정 수용 |

새 직접 비교의 사전 순서는 BASE/COMBINED, COMBINED/BASE, BASE/COMBINED였다. 이전 run을 새 쌍으로 조합하거나 두 개선율을 곱하지 않았다.

| 쌍 | 원본 → 결합본 Auto CPS | 평균 gap 개선율 | CPU/입력 변화 |
| --- | --- | --- | --- |
| 1 | 5.031220 → 5.788274 | 13.0791% | +3.8567%, +6.967ms |
| 2 | 5.151776 → 5.765701 | 10.6479% | +8.2353%, +14.630ms |
| 3 | 5.073028 → 5.796701 | 12.4842% | +2.7778%, +4.976ms |

BASE 변동 2.365030%에 대해 기준 max(5%,1.25×변동)=5%, 개선 중앙값 **12.484226%**다. 결합 세 판 모두 5.7–6.3 CPS, early 0, 최소 0.9P를 지켰다. P95/P99/max 9개 값이 모두 감소했다. CPU 증가 중앙값은 **+3.856749%, +6.966561ms**로 사전 기준(15%와 4 ms 동시 초과)에 해당하지 않았다. CPU는 관측 구간과 입력 수에 따른 값이며 독점 원인 기여로 해석하지 않는다.

주 CPS는 Auto 157개에 대해156/(마지막−첫 실제 입력 직전 시각(ns))다. 수동 OPEN(0,0) prefix, first 2 / 이후 155, Counters 전체 게임 시간, 사후 Replay CPS를 구분했다. 완전 창 peak 8/7 CPS는 이산 관측이며 안정 상한이 아니다.

Windows Qt의 같은 30×16/99 고정 배치, 수동 prefix 1 뒤 ADOPT_CURRENT, 추측OFF, 분석·확률·커서ON, 셀 28 px 조건이다. 23개 timing run 전체에서 action/좌표/Model C 비용/M 순서가 같고 각 Auto 157·Replay158·ACK157·WON이었다. 측정 전 ZiNi 113 준비 조건과 cold native를 분리했다. 외부 부하와 전시 노트북은 이 비교에서 입증하지 않았다.

## 4. 검토·반영·테스트 버전

`review_claude_01`은 원시 산술·identity·실행 정리를 재계산하고 A ACCEPT_BOUNDED / B ACCEPT / C CONDITIONS_REMAIN으로 판정했다. CROSSCHECK 121행 중 MATCH 113, MISMATCH 0이며 나머지는 미확인·PENDING·보존 FAIL 등이다. 제품 필수 수정 0, helper 필수 H1 1건, 비차단 선택 5, 정보 3이다.

| 근거 | 구분 |
| --- | --- |
| 원 `codex_01` | 28개 메서드·표시126건 통과. ACK 시험 등록명 오류로 전체 focused FAIL 유지 |
| `codex_02` S01 | 정확한 `test_failed_ack_cannot_reapply_consumed_token` 1개 별도 PASS |
| `codex_03` R2 | 같은 검토 source에서 미실행 mock 메서드56개 별도 PASS, 실패/오류/skip 0. 실제 subprocess 시도 0, owner 0, offscreen |

위 기록을 단일 전체 suite로 합치지 않는다. 최종 반영은 snapshot SHA256 네 개와 source 335 전체를 대조했다. 새 테스트 본문·제품 로직·성능 측정은 반영 단계에서 추가하지 않았다.

H1은 모든 Git 읽기에 `diff.autoRefreshIndex=false`, optional-locks0, command-local safe.directory를 적용하고, 모든 읽기 뒤 최종 index 해시를 기록하는 방식으로 완료했다. START/FINAL 각9회, 총18회 읽기 전후 index는 `bf95a31d39a9bd7d1b8c9ec2249a18d8a6ea85fa7d2e197a6e42bf81933c8c10`으로 같았다.

## 5. 사용자 native 수용과 참고 관측

검토된 네 파일이 적용된 상태임을 조율에서 재확인한 뒤, 사용자는 K-LC1의 외부 Auto ON/OFF, 고정6·Model C2배·거리1.5배의 진행/중단, 기본 Replay 종료와 같은 보드 종료 뒤 세 선호 및 Auto OFF 보존 안내에 **“좋아, 모두 통과야.”**라고 답했다.

이는 이번 PC에서 안내된 기능의 수용이다. 실제 판 수·정확한 클릭 수·기기 모델/OS/DPI·전체 처리량을 추가로 추정하지 않는다. 전시용 노트북은 아직 PENDING이다.

사용자는 별도로 **“10 CPS도 진행해봤는데 최대 8~9 CPS 안팎 정도는 나오는 것 같다”**고 보고했다. 원시 Replay, 관측 구간, 입력 수, metric 종류가 제공되지 않았으므로 비정형 참고 관측으로 보존한다. 이를 안정 상한, 새 benchmark PASS, 후보 전후 개선율 또는 모든 기기 보장으로 쓰지 않는다.

## 6. 실행·실패·선택 권고 이력

- 원 `codex_01`: Python 40/48, owner 18/28, outer 22 / OS 120. 정지 시 incident 8/8, 마감 포함 9/8. 원 전체 PARTIAL·두 후보 미채택·focused FAIL 유지.
- 보완 `codex_02`: Python 17/22, owner 7/10, outer 9 / OS 51, 실제 ZiNi child 포함. 정지 시3/3, 마감 포함 5/3. 원 S03·END raw-byte gate의 PARTIAL/FAIL 유지.
- 반영 `codex_03`: Python 1, owner 0, OS 3/3 정리. H1 완료, R2 별도 56 PASS. 마감 집계 helper 오류 1건 보정 기록을 유지한다.
- S03에서는 cold ZiNi 113, fixed 4회·정확 ACK 4회, Qt checkbox OFF 뒤 추가 입력 0, graph 9/9 정리까지 확인했다. Computer Use 앱 접근 승인 시간 초과로 외부 클릭은 0이었다. 자동 sandbox 심사 거절이나 제품 결함으로 바꾸지 않는다. 남은 사용자 조작은 이후 위의 직접 native 수용으로 채웠다.
- 과거 index 6a59→f0ff→bf95 변화 중 후자는 원복된 3파일의 mtime cache와 SHA-1 trailer 38 bytes였다. 399 path/mode/OID는 같다. Git stat-refresh와 기록이 일치하지만 쓰기 PID는 미확정이며 과거 raw-byte FAIL은 유지한다.
- R1 정확 복사·R2 제한된 추가 시험은 완료. R3 새 event-loop/guard 시험과 R5 추가 CPU 귀속은 보류. R4 전시 노트북은 PENDING. 정보 I1–I3과 이전 선택 권고 전체를 CLOSED로 만들지 않는다.

## 7. evidence와 마감

외부 root: `C:\Users\User\Documents\ChatGPT\졸업프로젝트\outputs\MAIN_LIVE_NATIVE_FIXED6_OPTIMIZATION_2026-11-06`.

| 묶음 | OUTPUT_MANIFEST SHA256 |
| --- | --- |
| codex_01, 580파일 | `71548de8dfdea9a3d98c07d23c1b26e59035c70dcb53df4167c0cd38c3fdd226` |
| codex_02, 318파일 | `32c5cd4d20af15ee57fc419dc57d2cbb38c3927ae2c9d9f1bbdfc7ebc5654717` |
| review_claude_01, 23파일 | `a66ecd790a0faec50bf0a3678f13591960898560351408711048e428516e4795` |
| codex_03, 97파일 | `09d645bb93def7377d2b14622df8fd4ab7d2fcbd87d4f1d5414c275948814654` |

이번 문서 준비는 현재PC native 수용 뒤 source/tests 6 + 문서 7의 한 묶음 Git 마감과 이후 Desktop recovery 교체를 준비하는 단계다. 실행·검토·native·commit은 서로 다른 receipt로 결속한다. 과거 완료된 Git/교체 스크립트는 재실행하지 않는다. 이후 receipt가 현재 Git authority이며 postcommit 문구만을 위한 추가 commit을 만들지 않는다.

D0–D5 CLOSED/FINAL ACCEPTANCE PASS, V1 CLOSED/FROZEN, Extended ACTIVE, PHASE1_INCONCLUSIVE_TRANSFER, effectiveness NOT ESTABLISHED를 유지한다. Production K/Gate P 및 Phase2/R0-B/ActualE2 미승인·미실행, B1 NOT_SATISFIED, F02 NOT_VERIFIED, 과거 Qt shared FileDialog FAIL/TEMP NOT_VERIFIED도 유지한다. frozen 정책/원 Model C/holdout2,010,000..2,010,099/금지 formal evidence를 열지 않는다. 추가 정책·공식·표본 추천과 Stage4는 별도 선택 범위다.
