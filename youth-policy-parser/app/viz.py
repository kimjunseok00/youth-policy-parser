"""탈락 사유 트리 → Graphviz DOT 문자열 (st.graphviz_chart로 그림).

DOT 문자열만 만들기 때문에 서버에 graphviz 프로그램을 설치할 필요가 없다 (브라우저에서 그림).
"""

from __future__ import annotations

from engine.schemas import ReasonNode, Verdict

# 판정별 색 (밝은 배경 / 테두리 / 글자 표시). 색만으로 구분하지 않도록 판정 이름을 앞에 붙인다.
# 색은 .streamlit/config.toml의 판정 색과 같은 계열이다.
STYLE = {
    Verdict.PASS: ("#EAF3EC", "#1E6B3A", "[충족]"),
    Verdict.FAIL: ("#F8EAEA", "#A32B2B", "[불충족]"),
    Verdict.UNKNOWN: ("#F6EFE0", "#8A5A00", "[확인 필요]"),
}
NOTICE_STYLE = ("#F4F6F9", "#5B6573", "[참고]")


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _wrap(text: str, width: int = 18) -> str:
    """한 줄이 너무 길면 줄바꿈 (DOT는 자동 줄바꿈을 하지 않는다)."""
    lines, cur = [], ""
    for word in text.split(" "):
        if cur and len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return "\\n".join(_esc(x) for x in lines)


def reason_to_dot(tree: ReasonNode, title: str = "") -> str:
    """사유 트리를 왼쪽→오른쪽 그래프로. 루트에는 정책 이름(title)을 쓴다."""
    out = [
        "digraph G {",
        "  rankdir=LR;",
        '  node [shape=box, style="filled", fontname="Pretendard, sans-serif", fontsize=11, '
        'fontcolor="#1B2430"];',
        '  edge [color="#9AA5B1"];',
    ]
    counter = [0]

    def add(node: ReasonNode, label: str) -> str:
        nid = f"n{counter[0]}"
        counter[0] += 1
        fill, border, mark = NOTICE_STYLE if node.notice else STYLE[node.verdict]
        text = f"{mark} {_wrap(label)}"
        if node.detail and not node.children:
            text += f"\\n— {_wrap(node.detail, 22)}"
        out.append(f'  {nid} [label="{text}", fillcolor="{fill}", color="{border}"];')
        for child in node.children:
            out.append(f"  {nid} -> {add(child, child.label)};")
        return nid

    add(tree, title or tree.label)
    out.append("}")
    return "\n".join(out)
