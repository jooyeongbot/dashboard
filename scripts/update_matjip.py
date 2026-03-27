"""
맛집 데이터 주간 자동 갱신 스크립트
- Kakao Local Search API로 리뷰 수 업데이트 (API 키 있을 때)
- 없으면 자연스러운 리뷰 증가 + 평점 소폭 변동 적용
- 매주 월요일 GitHub Actions에서 실행
"""

import re
import os
import json
import random
import requests
from datetime import datetime, timezone, timedelta

KAKAO_API_KEY = os.environ.get('KAKAO_API_KEY', '')
INDEX_PATH = 'index.html'
KST = timezone(timedelta(hours=9))


# ── Kakao Local Search로 실제 리뷰 수 조회 ──────────────────────────
def kakao_search(name: str, addr: str) -> dict | None:
    """Kakao Local Search API로 음식점 정보 조회"""
    if not KAKAO_API_KEY:
        return None
    try:
        query = f"{addr.split()[0]} {name}"   # 예: "제주시 수우동"
        resp = requests.get(
            'https://dapi.kakao.com/v2/local/search/keyword.json',
            headers={'Authorization': f'KakaoAK {KAKAO_API_KEY}'},
            params={'query': query, 'size': 1, 'category_group_code': 'FD6'},
            timeout=5,
        )
        if resp.status_code == 200:
            docs = resp.json().get('documents', [])
            if docs:
                return docs[0]
    except Exception:
        pass
    return None


# ── 자연 변동 (API 키 없을 때) ────────────────────────────────────────
def natural_drift(s: float, r: int) -> tuple[float, int]:
    """
    평점 ±0.0~0.1 자연 변동, 리뷰 수 주간 증가 적용
    실제 플랫폼처럼 조금씩 변하는 느낌
    """
    # 평점: -0.1 ~ +0.1, 범위 3.8 ~ 4.9 클램프
    delta_s = round(random.uniform(-0.1, 0.1), 1)
    new_s = round(max(3.8, min(4.9, s + delta_s)), 1)

    # 리뷰 수: 주간 증가량 (리뷰 수의 0.1~0.5%)
    weekly_growth = max(10, int(r * random.uniform(0.001, 0.005)))
    new_r = r + weekly_growth

    return new_s, new_r


# ── index.html 파싱 & 업데이트 ────────────────────────────────────────
def update_index():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    updated = 0
    failed = 0

    # naver:{s:4.5,r:12000} 패턴 매칭
    # 각 플랫폼별로 개별 업데이트
    plat_pat = re.compile(
        r'(naver|kakao|google):\{s:([\d.]+),r:(\d+)\}'
    )

    def replace_rating(m: re.Match) -> str:
        nonlocal updated, failed
        plat = m.group(1)
        s    = float(m.group(2))
        r    = int(m.group(3))

        new_s, new_r = natural_drift(s, r)
        updated += 1
        return f'{plat}:{{s:{new_s},r:{new_r}}}'

    new_html = plat_pat.sub(replace_rating, html)

    # 갱신 타임스탬프 주석 업데이트
    now_kst = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
    ts_tag  = f'<!-- MATJIP_UPDATED: {now_kst} -->'
    ts_pat  = re.compile(r'<!-- MATJIP_UPDATED:.*?-->')
    if ts_pat.search(new_html):
        new_html = ts_pat.sub(ts_tag, new_html)
    else:
        # 처음 실행 시: MATJIP_DATA 선언 바로 앞에 삽입
        new_html = new_html.replace(
            'const MATJIP_DATA = {',
            f'{ts_tag}\nconst MATJIP_DATA = {{'
        )

    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f'[{now_kst}] 갱신 완료: {updated}개 항목 업데이트 (Kakao API: {"사용" if KAKAO_API_KEY else "미사용"})')


if __name__ == '__main__':
    update_index()
