"""앱 레이어 공개 인터페이스.

화면(streamlit_app.py)은 이 모듈의 get_results()만 호출한다.
엔진 완성 후 get_results() 내부만 engine 호출로 교체하면 되므로
화면 코드는 손댈 필요가 없다.
"""

from pathlib import Path

from engine.schemas import EvaluationResult, Profile

_MOCK_PATH = Path(__file__).parent.parent / "data" / "mock" / "mock_results.json"


def get_results(profile: Profile) -> EvaluationResult:  # noqa: ARG001
    """프로필을 받아 판정 결과를 반환한다.

    현재는 data/mock/mock_results.json을 읽어 스키마로 검증 후 반환한다.
    엔진 완성 후 이 함수 내부만 engine 호출로 교체한다.
    profile 인수는 엔진 교체 시 쓰이므로 지금은 사용하지 않는다.
    """
    return EvaluationResult.model_validate_json(_MOCK_PATH.read_text(encoding="utf-8"))
