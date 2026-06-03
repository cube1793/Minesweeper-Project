# Minesweeper Project

Python과 PyQt5 기반의 지뢰찾기 졸업프로젝트입니다.

## 목표

1. 지뢰찾기 UI/UX 구성 및 리플레이 구현
2. 단순 알고리즘 구현
3. 속도 위주 알고리즘 구현
4. 효율 위주 알고리즘 구현
5. 속도 위주 AI 구현
6. 효율 위주 AI 구현

## 실행 방법

```powershell
pip install -r requirements.txt
python main.py
```

## 현재 상태
- PyQt5 기반 지뢰찾기 UI 구현
- 핵심 게임 엔진 구현
- 3BV/Ops 및 클릭 통계 일부 구현 
- ZiNi는 아직 안정 구현 전

## 개발 방향

현재는 ZiNi 구현 전 안정 버전을 main 브랜치에 유지한다.

잘못된 ZiNi 임시 구현은 experiment/zini-prototype-broken 브랜치에 보관한다.

앞으로 ZiNi는 별도 분석 모듈로 분리하여 구현할 예정이다.

본 프로젝트는 소프트웨어공학 원칙을 준수하여 확장성, 유지보수성, 테스트 가능성을 고려해 개발한다.