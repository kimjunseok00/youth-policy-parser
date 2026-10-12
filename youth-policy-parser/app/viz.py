"""탈락 사유 트리 → Graphviz DOT 문자열 (st.graphviz_chart로 그림).

DOT 문자열만 만들기 때문에 서버에 graphviz 프로그램을 설치할 필요가 없다 (브라우저에서 그림).
"""

from __future__ import annotations

from engine.schemas import ReasonNode, Verdict

# 판정별 색 (밝은 배경 / 테두리). 색만으로 구분하지 않도록 라벨 앞에 기호도 붙인다.
STYLE = {
    Verdict.PASS: ("#e6f4ea", "#2f7d4f", "✔"),
    Verdict.FAIL: ("#fde8e7", "#b3362f", "✘"),
    Verdict.UNKNOWN: ("#fdf1dc", "#a8650b", "?"),
}


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
        '  node [shape=box, style="rounded,filled", fontname="sans-serif", fontsize=11];',
        '  edge [color="#9aa5b1"];',
    ]
    counter = [0]

    def add(node: ReasonNode, label: str) -> str:
        nid = f"n{counter[0]}"
        counter[0] += 1
        fill, border, mark = STYLE[node.verdict]
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
