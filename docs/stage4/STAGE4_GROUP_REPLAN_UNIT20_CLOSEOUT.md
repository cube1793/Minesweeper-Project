# Stage 4 Unit20 그룹 경계 재계획 마감

## 판정과 범위

2026-11-08에 A/B와 신규 C 한 판의 묶음 독립 검토를 마쳤다. 제품/전달은 ACCEPT_BOUNDED, A의 저장 경로 재사용은 ACCEPT_CONDITIONAL, 회계/실행은 ACCEPT다. C의 NO_IMPROVEMENT를 독립 엔진 재생과 원시에서 확인했다. 필수 수정은 0건이며 비차단 6건과 미확인 항목을 보존한다.

후보 SAFE_GROUP_REPLAN_V1은 output 영역의 prototype이다. 입력 수 개선이 없어 NOT_ADOPTED로 마감하며 제품 source에는 반영하지 않는다. Stage4 전체는 NOT_MERGED이고 일반 효과성은 NOT ESTABLISHED다. 이전 범위는 [Units18–19/R1 마감](STAGE4_EFFICIENCY_EXPERIMENTS_UNITS18_19_CLOSEOUT.md)을 따른다.

시험·C 실행 및 이 문서 갱신의 출발 HEAD는 `624854a26d426f9886c6d65b80e9c3d64acbddac`다. source365·출발 tracked446을 확인했다. 이번 문서6경로 마감 후 tracked447을 예상하며 실제 commit/push와 Desktop destination은 별도 영수증으로 확인한다. 문서 커밋을 시험 실행 HEAD로 소급하지 않는다.

## 후보의 동작

Unit18의 후보·비용식·정렬과 Q를 유지하고, READY·override·여러 그룹인 결정에서 첫 그룹만 예약한다. 그룹 안의 준비 FLAG 또는 해제와 마지막 CHORD/OPEN은 끝까지 처리하며 그 사이 Q를 호출하지 않는다. 그룹이 끝나면 실제 공개 격자와 counted를 바탕으로 fresh Q를 호출한다.

원 계획의 나머지는 감사 자료로만 보관한다. PendingMacro는 예약한 첫 그룹만 받아 원 tail을 큐에 보유하지 않는다. 기존 identity·instance·관측·원장·count·기한·terminal·안전/지뢰 proof와 CHORD guard를 유지한다. 이미 수행한 FLAG 비용은 실제 counted에 남는다.

## 제한 비교

| 판 | Unit18 기준 | Unit20 | 근거 |
| --- | --- | --- | --- |
| E01 | WON / 163 | WON / 163 | A 승인 저장 경로 재사용 |
| E02 | WON / 173 | WON / 173 | 신규 C 한 판 |
| E03 | LOST / 3 | LOST / 3 | A 승인 저장 경로 재사용 |
| E04 | LOST / 2 | LOST / 2 | A 승인 저장 경로 재사용 |

신규 E02는 일반 first OPEN(0,0)부터 173입력으로 승리했다. 종료 후 3BV177과 IOE177/173을 확인했다. 주 기준 Unit18 C173 대비 실제 차이는0이다. Unit19 C175와 Unit15 C174는 참고값이다. 신규 네 판 실행이나 네 승으로 기록하지 않는다.

Unit18과의 입력 차이는 C83..C112의30곳, 공개 after 관측 차이는 C83..C111의29곳이다. C112에서 같은 공개 상태로 합쳐진다. 전체 입력 multiset 차이는 CHORD(17,11) 한 번이 OPEN(17,12) 한 번으로 바뀐 것이다. 순서와 선택이 달라졌지만 counted는 줄지 않았다. 한 판의 경로 관측을 정책 효과 추정으로 확대하지 않는다.

C의 원 감사계획 합178 = 예약172 + 미예약6이며 예약172 = 실제172 + skip0 + 오류 폐기0이다. 첫 OPEN1을 더해 최종173이다. 미예약6이나 감사계획178을 실제 절약량 또는 비교 기준으로 쓰지 않는다. 두 번째 원 tail4입력은 fresh Q가 다시 선택했으며 이전 큐에서 실행한 것이 아니다.

## A/B와 독립 확인

- AST14는 위치정보 없는 구조 비교와 알려진 분기 정규화를 확인했다. 실제 신/구 비어 있지 않은 경로가 같았고, guard 제거·deliver 대상·count 증가·enumerate·이벤트 변경의 음성 대조5건을 검출했다. 일반 실행 동등성 증명이 아니다.
- A279의 변환은 Unit18 저장 E02 Q67의4입력/3그룹→2입력과 Q126의7입력/5그룹→3입력 두 곳뿐이다. 나머지277건은 항등이다. E01/E03/E04 재사용은 source·초기 상태·RNG·설정·skip0 및 비어 있지 않은 경로에 대한 귀납이며, bounded Q가 저장처럼 완료한다는 조건이 붙는다.
- B34는 각1회 통과했다. 실제 Q4/counter2/engine16, 통제 전이30을 구분한다. 실제5×3 엔진 fixture 두 개의 첫 J는 통제 선택이며 자연 Unit18 선택의 증거가 아니다.
- 운영 소유 조회13시험은 조율의 별도 읽기 전용 PowerShell 시험이다. AST14 또는 B34에 합치지 않는다. H1의 큰 정수·Fraction·null은 초기와 종료 저장 왕복을 확인했다.
- C의 변환은 Q67과 Q128이다. Q145개·fresh 경계144개, 준비 FLAG 사이 Q0, terminal 뒤 Q/입력0과 계획·요청 hash를 확인했다. 실제2.0 토큰145개를 보존해 identity를 독립 재계산했다.
- 독립 검토는 C173입력과 Unit18 E02의173입력을 각각 재생했다. 엔진 전이 총514/5000, C 관측·승패·layout·첫 관측·3BV·IOE 불일치0이다. unchanged Q/Unit10 확률 수학은 이전 독립 수용에 의존한다.

## 비용과 실행 이력

| 실제 비용 | A/B | C | 누적 |
| --- | ---: | ---: | ---: |
| Q | 4 | 145 | 149 |
| counter | 2 | 14 | 16 |
| engine 입력 | 16 | 173 | 189 |
| adapter 변환 | 321 | 145 | 466 |
| 통제 전이 | 30 | 0 | 30 |
| Q local | 442 | 545402 | 545844 |
| Unit10 units | 10882 | 82203 | 93085 |

이월은 한 번만 적용됐고 원시 예약·정산과 합이 일치했다. C의 Unit10은 primary2580 + auxiliary79623 =82203이다. 미확정 예약과 pending은0이다. Q139→145 등 다른 실행의 비용을 속도 개선의 근거로 사용하지 않는다.

원 START3/3·실제 image4·보수 image6/6은 소진된 역사다. 별도 C START1/image2를 더해 전체 START4·실제 image6·보수 image8이다. 원 실패에서 생성되지 않은 image의 보수 차감과 실제 생성은 구분한다.

codex_01의 실행 전 host 읽기 권한 실패, codex_02의 A AST 검사 실패, codex_03의 이전 소유 PID getter null 오류를 보존한다. codex_04에서 AST/A/B를 통과했고 codex_05는 C만 한 번 실행했다. 과거 실패를 소급 PASS로 바꾸지 않는다. 원 incident6/6, R3 0/2, C 3/3 및 각 읽기/helper 보정 pool도 별도로 남긴다.

## 비차단 처분과 미확인

- U20R-N1. A의 E02.reason은 공통 템플릿 문구라 changed_sites 및 reuse_approved=false와 모순된다. 마감 해석은 명시 필드에 따른다. 원 JSON은 보존한다.
- U20R-N2. C 정리의 TerminateJobObject 호출1회를 기록한다. 세 member의 exit가 모두0이고 요청238은 관측되지 않았다. 강제 종료는 입증되지 않으며 호출 시 active1의 정체는 conhost로 추정될 뿐이다. Job terminated0은 한도 위반 종료 계수여서 이 판단의 근거로 쓰지 않는다.
- U20R-N3. C 승인 파일의 utc03:40:44Z는 생성 시각이다. I02 보정 중03:45:40Z에 승인 파일이 갱신됐고 보정 전 사본은 없다. 최종 bytes는03:47:07Z 등록과03:47:27Z START보다 앞서 동결됐고 조율 범위·예산과 일치했다.
- U20R-N4. 일부 receipt/result/CARRY의 true/false 및 application_count=1은 구조적 보장이다. 측정 필드로 소개하지 않으며 실제 분할·fresh 경계·이월 원시의 재도출 결과와 구분한다.
- U20R-N5. effective no_new_python04:38:55Z가 closeout04:08:55Z보다 늦은 표시 순서를 보존한다. 실제 START03:47:27Z와 마감04:00:34Z는 더 이른 경계 안이었다. 원시를 고치지 않는다.
- U20R-N6. counter의 max_seconds는 잔여 시간이므로 같은 공개 상태에서도 Q 결과 bytes/result_hash가 실행 간 달라질 수 있다. 재사용은 결정 단위의 조건부 동일성이다. 실행 간 Q 응답 byte 동일성을 주장하지 않는다.

E01/E03/E04를 실제 다시 실행한 결정성, TJO 시점의 구성원·teardown 효과, codex_02 당시 보존되지 않은 AST 차이, codex_03 null의 정확한 OS 원인, 실제 세션 설정은 미확인으로 남긴다. 현재 PC의 사용자 native나 전시 노트북 수용을 이 검토에서 추가하지 않았다.

## 마감과 후속

독립 검토의 필수 보완은0이다. 이번 후보는 NOT_ADOPTED로 기록만 마감한다. 다음 전략·일반 S/M/R 평가·메인/worker·전시 노트북·패키지는 별도 범위이며, 이번 검토로 시작하지 않는다. D0–D5/V1/Model C/frozen 정책·holdout·연구 승인과 이전 실패 경계를 유지한다.

근거는 `C:/Users/User/Documents/ChatGPT/졸업프로젝트/outputs/STAGE4_GROUP_REPLAN_UNIT20_2026-11-08/` 아래 codex_01~05, coordinator_01~06, review_claude_01에 있다. 구현 원시857파일/19818833 bytes, 독립 검토25파일/361331 bytes를 각각 결속했다. 검토 manifest SHA256은 `385176d56ae04fd8db8a901f3374bae06c0eaf1b881d9467c221a7ed4244c887`이다. Git·Desktop 마감은 별도 영수증을 현재 authority로 삼는다.
