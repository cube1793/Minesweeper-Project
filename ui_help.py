"""Read-only help for the existing Main/Live controls and statistics."""

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QTableWidget, QTabWidget, QTextBrowser, QToolTip,
    QVBoxLayout,
)

from live_k_basis import HELP_LINES as K_HELP_LINES


STAT_TOOLTIPS = {
    "time": "게임 경과 시간입니다.\nReplay에서는 현재 재생 시점의 시간을 표시합니다.",
    "est_time": "현재 3BV 처리 속도가 유지된다고 가정한 예상 완료 시간입니다.\n남은 시간이 아니라 전체 예상 시간입니다.",
    "bbbv": "화음 없이 보드를 여는 데 필요한 클릭 수를 기준으로 한 난이도 지표입니다.\n해결한 3BV / 전체 3BV를 표시합니다.",
    "bbbv_per_sec": "초당 해결한 3BV입니다.\n해결한 3BV ÷ 경과 시간으로 계산합니다.",
    "clicks": "Left·Right·Chord를 합한 전체 입력 횟수입니다.\n종료 후 A + B 표시는 유효 클릭 + 낭비 클릭입니다.",
    "left": "칸 열기 입력 횟수입니다.\n종료 후 A + B 표시는 유효 클릭 + 낭비 클릭입니다.",
    "right": "깃발을 꽂거나 해제한 입력 횟수입니다.\n종료 후 A + B 표시는 유효 클릭 + 낭비 클릭입니다.",
    "chord": "열린 숫자의 주변 칸을 함께 여는 화음 입력 횟수입니다.\n종료 후 A + B 표시는 유효 클릭 + 낭비 클릭입니다.",
    "cps": "초당 실제 입력 횟수입니다.\n전체 클릭 수 ÷ 경과 시간이며, 설정한 목표 CPS와 다를 수 있습니다.",
    "efficiency": "해결한 3BV ÷ 전체 클릭 수 × 100으로 계산한 입력 효율입니다.\n120%는 클릭당 평균 1.2의 3BV를 해결했다는 뜻입니다.",
    "ioe": "입력 효율을 소수로 표시한 값입니다.\nEfficiency 120%는 IOE 1.2입니다.",
    "ops": "해결한 자동 펼침(오프닝) 영역 수 / 전체 영역 수입니다.",
    "thrp": "해결한 3BV ÷ 유효 클릭 수입니다.\n낭비 클릭을 제외한 입력 효율입니다.",
    "corr": "유효 클릭 수 ÷ 전체 클릭 수입니다.\n낭비 클릭이 없으면 1입니다.",
    "zini": "보드 배치를 아는 별도 계산으로 얻은 기준 클릭 수입니다.\n실제 플레이의 클릭 수나 보장된 최소 클릭 수와는 다릅니다.",
    "zne": "ZiNi ÷ 전체 클릭 수입니다.\n계산 결과가 없거나 분모가 0이면 -로 표시합니다.",
    "znt": "ZiNi ÷ 유효 클릭 수입니다.\n계산 결과가 없거나 분모가 0이면 -로 표시합니다.",
}


class StatisticsTable(QTableWidget):
    """Keep a statistic's tooltip within the hovered label or value cell."""

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            item = self.itemAt(event.pos())
            if item is not None and item.toolTip():
                QToolTip.showText(event.globalPos(), item.toolTip(), self.viewport(),
                                  self.visualItemRect(item))
                event.accept()
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        if event.type() in (QEvent.Leave, QEvent.Hide):
            QToolTip.hideText()
        return super().viewportEvent(event)


# K_D23: the static help lines live in the parent-safe basis module.
K_HELP_HTML = ("<h2>K의 선택 이유와 진단 읽는 법</h2><ul>"
               + "".join(f"<li>{line}</li>" for line in K_HELP_LINES) + "</ul>")

HELP_PAGES = (
    ("기본 조작", """
        <h2>게임 시작과 기본 조작</h2>
        <p>위쪽에서 난이도와 셀 크기를 고릅니다. 웃는 얼굴 버튼은 새 게임을 시작합니다.
        일반 창으로 사용하거나 필요할 때 창을 최대화할 수 있습니다.</p>
        <ul>
          <li><b>좌클릭:</b> 닫힌 칸을 엽니다.</li>
          <li><b>우클릭:</b> 지뢰로 예상하는 칸에 깃발을 꽂거나 해제합니다.</li>
          <li><b>화음(CHORD):</b> 열린 숫자의 주변 깃발 수가 숫자와 같을 때,
          주변의 깃발 없는 칸을 함께 엽니다. 깃발 위치가 틀리면 지뢰가 열릴 수 있습니다.</li>
        </ul>
        <h3>화음 방식</h3>
        <p><b>모드 A:</b> 열린 숫자에서 좌클릭 또는 좌우 동시 클릭.<br>
        <b>모드 B:</b> 좌우 동시 클릭.<br>
        <b>모드 C:</b> 화음 사용 안 함.</p>
        <h3>화면의 분석 표시</h3>
        <p><b>현재 상태 분석</b>은 추천을 표시하며 그 자체로 입력하지 않습니다.
        <b>분석 표시</b>는 분석 결과를, <b>확률 표시</b>는 계산된 지뢰 확률을 표시합니다.
        <b>Reduction</b>은 열린 숫자를 ‘숫자에서 주변 깃발 수를 뺀 값’으로 표시하는 옵션입니다.</p>
        <p>도움말을 여는 것만으로 진행 중인 Auto나 Replay가 일시정지되지는 않습니다.
        천천히 읽으려면 먼저 진행을 멈춰 주세요.</p>
    """),
    ("알고리즘·속도", """
        <h2>Auto 알고리즘</h2>
        <p>알고리즘을 고른 뒤 자동 진행을 켭니다. <b>선택 정책으로 새 게임</b>은
        선택한 알고리즘으로 사용할 새 판을 시작합니다. 정책을 바꾸면 Auto는 멈춥니다.</p>
        <ul>
          <li><b>Stage2 Simple:</b> 공개된 숫자에서 확정 수를 찾고, 필요하면 지뢰 확률을 계산합니다.</li>
          <li><b>Stage3 V1:</b> 확정된 수 중 이동과 입력 비용을 고려해 다음 행동을 고릅니다.</li>
          <li><b>K-P0 / K-LC0 / K-LC1:</b> 서로 다른 추론·선택 방식을 적용한 Stage3 계열 정책입니다.</li>
          <li><b>K:</b> K-LC1의 선택에 증명된 오프닝 우선, 불가피한 50/50 먼저 처리, 동률 전방 비교를 더한
          정책입니다. 상태 줄에 선택 이유가 나오고 <b>K 설명</b> 단추로 상세 설명을 펼칩니다.</li>
          <li><b>Stage4 S / M / R:</b> 입력 효율을 고려하는 세 가지 선택 방식입니다.
          S는 안전성 기준을, M은 평균 성과를, R은 지정한 목표 효율의 도달을 우선합니다.</li>
        </ul>
        <p><b>추측 허용</b>을 켜면 확정 수가 아닌 위험한 입력도 선택할 수 있습니다.
        S를 선택해도 추측을 허용한 플레이의 승리가 보장되지는 않습니다.
        R의 목표값 역시 달성 보장이 아닙니다.</p>
        <h3>속도 방식</h3>
        <ul>
          <li><b>고정 간격:</b> 자동 입력의 목표 간격 또는 CPS를 정합니다.</li>
          <li><b>Model C 기반:</b> 이동·입력 비용 모델의 시간을 관람 배속에 맞춰 사용합니다.</li>
          <li><b>거리 기반:</b> 이동 거리를 반영해 관람 속도를 조절합니다.</li>
        </ul>
        <p>계산·통신 시간이 필요하므로 <b>목표 CPS</b>와 실제 <b>CPS</b>는 다를 수 있습니다.
        비활성화된 옵션은 현재 정책이나 화면에서 사용할 수 없는 옵션입니다.</p>
        <p><b>자동 커서 표시</b>는 지원하는 자동 정책의 입력 위치를 보여 주는 가상 표시입니다.
        실제 마우스 경로 기록과는 별개입니다.</p>
    """),
    ("통계", """
        <h2>왼쪽 Counters 읽기</h2>
        <p>항목명이나 값 위에 마우스를 올리면 짧은 설명이 나타나고,
        마우스를 옮기면 사라집니다. 자세한 뜻과 계산식은 아래에서 확인하세요.</p>
        <p>진행 중에는 일부 지표를 <b>-</b> 또는 <b>-/-</b>로 표시합니다.
        종료 후에도 계산 결과가 없거나 분모가 0이면 표시하지 않습니다.</p>
        <p>완료 기록의 클릭 수가 <b>A + B</b>로 보이면 A는 유효 클릭, B는 낭비 클릭입니다.
        아래의 전체 클릭 수는 둘을 합한 값입니다.</p>
        <table border="0" cellspacing="7" cellpadding="3">
          <tr><td><b>Time</b></td><td>게임 경과 시간. Replay에서는 기록의 현재 시점입니다.</td></tr>
          <tr><td><b>Est Time</b></td><td>현재까지의 3BV 처리 속도가 유지된다고 가정한 전체 예상 시간입니다.</td></tr>
          <tr><td><b>3BV</b></td><td>화음 없이 보드를 여는 데 필요한 클릭 수를 기준으로 한 보드 난이도 지표.
          화면에는 해결한 양 / 전체 양을 표시합니다.</td></tr>
          <tr><td><b>3BV/s</b></td><td>해결한 3BV ÷ 경과 시간. 보드를 처리한 속도입니다.</td></tr>
          <tr><td><b>Clicks</b></td><td>전체 입력 횟수. Left·Right·Chord의 합입니다.</td></tr>
          <tr><td><b>Left / Right / Chord</b></td><td>칸 열기 / 깃발 입력 / 화음 입력 횟수입니다.</td></tr>
          <tr><td><b>CPS</b></td><td>전체 클릭 수 ÷ 경과 시간. 초당 실제 입력 횟수입니다.</td></tr>
          <tr><td><b>Efficiency</b></td><td>해결한 3BV ÷ 전체 클릭 수 × 100.
          승리하면 전체 3BV를 기준으로 합니다. 120%는 클릭당 평균 1.2의 3BV를 해결했다는 뜻입니다.</td></tr>
          <tr><td><b>IOE</b></td><td>Efficiency와 같은 비율의 소수 표기. Efficiency 120%는 IOE 1.2입니다.</td></tr>
          <tr><td><b>Ops</b></td><td>해결한 자동 펼침(오프닝) 영역 수 / 전체 영역 수입니다.</td></tr>
          <tr><td><b>Thrp</b></td><td>해결한 3BV ÷ 유효 클릭 수입니다.</td></tr>
          <tr><td><b>Corr</b></td><td>유효 클릭 수 ÷ 전체 클릭 수. 낭비 클릭이 없으면 1입니다.</td></tr>
          <tr><td><b>ZiNi</b></td><td>보드 배치를 아는 별도 계산으로 얻은 기준 클릭 수.
          실제 플레이한 클릭 수와 다릅니다.</td></tr>
          <tr><td><b>ZNE</b></td><td>ZiNi ÷ 전체 클릭 수입니다.</td></tr>
          <tr><td><b>ZNT</b></td><td>ZiNi ÷ 유효 클릭 수입니다.</td></tr>
        </table>
        <p>효율이 높다는 것이 승률이 높다는 뜻은 아닙니다. 승패와 함께 비교하세요.
        ZiNi 등 종료 후 보드 분석 결과는 자동 풀이의 다음 수를 고르는 입력이 아닙니다.</p>
    """),
    ("Replay·기록", """
        <h2>플레이 보관과 다시 보기</h2>
        <ul>
          <li><b>이번 판 Replay:</b> 현재 판의 기록을 Replay 화면에서 봅니다.</li>
          <li><b>Replay 저장 / 다른 이름으로 저장:</b> 기록을 JSON 파일로 보관합니다.</li>
          <li><b>Replay 불러오기:</b> 저장한 기록을 엽니다.</li>
          <li><b>같은 보드 다시 플레이:</b> 종료한 판의 같은 배치에서 새 플레이를 시작합니다.</li>
          <li><b>재플레이 전 기록:</b> 같은 배치에서 완료한 이전 기록을 확인합니다.</li>
        </ul>
        <p>보관할 판은 새 게임을 시작하기 전에 저장하세요. Replay 자동 재생은 기록된 입력을
        따라가는 기능이며, 알고리즘이 지금 새 수를 계산하는 Auto와 다릅니다.</p>
        <h3>마우스 경로</h3>
        <p><b>마우스 경로 기록</b>은 실제 포인터 움직임을 저장하는 옵션입니다.
        첫 입력 전에 선택하며, <b>마우스 경로 표시</b>로 종료된 판이나 Replay의 경로를 볼 수 있습니다.</p>
        <p>완료된 Replay에서는 현재 재생 시점의 진행량·클릭 수와 보드 전체 지표를 함께 표시합니다.
        미완료 기록의 일부 통계는 표시되지 않을 수 있습니다.</p>
    """),
    ("보조 도구", """
        <h2>플레이를 살펴보는 보조 도구</h2>
        <p>왼쪽 아래의 <b>ZiNi Explorer</b>는 계산된 ZiNi 경로를 따라
        현재 보드의 분석 결과를 살펴보는 도구입니다.
        분석 결과와 경로가 준비되지 않으면 버튼이 비활성화됩니다.</p>
        <h3>도구 → 일반 도구</h3>
        <ul>
          <li><b>Replay 저장 폴더:</b> 기본 기록 저장 위치를 설정합니다.</li>
          <li><b>같은 보드 비교(수동 플레이):</b> 완료된 수동 플레이 기록 전체를 같은 보드의
          Stage2 Simple·Stage3 V1 실행과 비교합니다. 비교 창이 이미 열려 있으면
          메뉴가 <b>비교 창 다시 열기</b>로 표시됩니다.</li>
        </ul>
        <p>현재 비교 대상은 Stage2 Simple과 Stage3 V1로 고정되어 있습니다.
        결과 창의 선택란은 보여 줄 실행 결과를 고릅니다. Stage3 K 계열과 Stage4 S/M/R은
        이 비교 도구에서 아직 지원하지 않습니다.</p>
        <h3>도구 → 개발자 도구</h3>
        <ul>
          <li><b>벤치마크 통계:</b> 저장된 벤치마크 결과를 비교·분석합니다.</li>
          <li><b>Stage-3 Visualizer:</b> 별도 기준 보드에서 Stage3 실행과 이동 경로를
          확인합니다. 여는 것만으로 현재 게임의 알고리즘이 바뀌지는 않습니다.</li>
        </ul>
        <p>개발자 도구는 실험·검토용이며, 일반 플레이에는 사용할 필요가 없습니다.</p>
    """),
    ("K 설명", K_HELP_HTML),
)


class HelpDialog(QDialog):
    """Modeless help: opening or closing it has no gameplay side effects."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("지뢰찾기 도움말")
        self.setModal(False)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        for title, content in HELP_PAGES:
            page = QTextBrowser(self.tabs)
            page.setOpenExternalLinks(False)
            page.document().setDefaultStyleSheet(
                "body { font-family: 'Segoe UI'; font-size: 10pt; }"
                "h2 { font-size: 14pt; } h3 { font-size: 11pt; }"
                "td { vertical-align: top; }"
            )
            page.setHtml(content)
            self.tabs.addTab(page, title)
        layout.addWidget(self.tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("닫기")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        available = self.screen().availableGeometry()
        self.resize(min(720, available.width() - 40), min(580, available.height() - 80))
