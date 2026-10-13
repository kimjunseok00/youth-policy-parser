"""API 키 연결 확인 스크립트.

엔드포인트 주소와 인증키 파라미터 이름을 코드에 고정하지 않고 .env에서 읽는다.
(공공데이터포털 활용신청 상세 화면에 나오는 값을 그대로 옮겨 적으면 된다)

.env 예시:
    ONTONG_API_KEY=발급받은_일반_인증키(Decoding)
    ONTONG_API_URL=활용신청_상세에_나오는_요청주소(End_Point)
    ONTONG_KEY_PARAM=serviceKey      # 명세에 적힌 인증키 파라미터 이름

실행:
    uv run --env-file .env python scripts/check_api.py
    uv run --env-file .env python scripts/check_api.py pageNo=1 numOfRows=3   # 추가 파라미터
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def mask(text: str, secret: str) -> str:
    """출력에 인증키가 그대로 찍히지 않도록 가린다. (캡처해서 공유해도 안전하게)"""
    if not secret:
        return text
    for s in {secret, urllib.parse.quote(secret, safe="")}:
        text = text.replace(s, s[:4] + "****")
    return text


def main() -> int:
    key = os.environ.get("ONTONG_API_KEY", "").strip()
    url = os.environ.get("ONTONG_API_URL", "").strip()
    key_param = os.environ.get("ONTONG_KEY_PARAM", "serviceKey").strip()

    # 1단계: .env가 제대로 읽혔는지부터 확인 (가장 흔한 실패 지점)
    missing = [name for name, v in [("ONTONG_API_KEY", key), ("ONTONG_API_URL", url)] if not v]
    if missing:
        print(f"[오류] .env에서 값을 못 읽었습니다: {', '.join(missing)}")
        print("   → --env-file .env 옵션을 붙였는지, 저장소 루트에서 실행했는지 확인하세요.")
        return 1
    print(f"[통과] .env 읽기 성공 (키 앞 4자리: {key[:4]}****, 파라미터 이름: {key_param})")

    # 2단계: 요청 만들기. 명령줄의 name=value 쌍을 추가 파라미터로 붙인다.
    params = {key_param: key}
    for arg in sys.argv[1:]:
        name, _, value = arg.partition("=")
        params[name] = value
    full_url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
    print(f"→ 요청: {mask(full_url, key)}")

    # 3단계: 호출하고 결과를 요약해서 보여준다.
    try:
        with urllib.request.urlopen(full_url, timeout=15) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"[오류] HTTP {e.code}: {mask(e.read().decode('utf-8', 'replace')[:500], key)}")
        print("   → 401/403이면 키 또는 파라미터 이름 문제, 404면 주소 문제입니다.")
        return 1
    except urllib.error.URLError as e:
        print(f"[오류] 연결 실패: {e.reason}  → 주소(ONTONG_API_URL)를 확인하세요.")
        return 1

    print(f"[통과] HTTP {status}, 응답 {len(body):,}자")
    try:
        data = json.loads(body)
        print("응답 형식: JSON")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    except json.JSONDecodeError:
        # XML이거나, 키 오류 메시지가 XML로 올 수 있다 (공공데이터포털에서 흔함)
        print("응답 형식: JSON 아님 (XML일 수 있음)")
        print(mask(body[:3000], key))
    print("\n위 출력(키는 가려져 있음)을 복사해서 공유하면 필드 분석을 진행할 수 있습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
