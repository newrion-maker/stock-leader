"""
주도 테마 분석기 - collect.py
================================
매일 장 마감 후 실행하세요 (오후 4시 이후 권장)

설치:
  pip install pykrx requests beautifulsoup4

실행:
  python collect.py
"""

import requests
from bs4 import BeautifulSoup
from pykrx import stock
from datetime import datetime, timedelta
import json, time, re

# ─────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────
TOP_N          = 60     # 거래대금 상위 몇 위까지 볼지
MIN_THEME_CNT  = 3      # 주도 테마 인정 최소 종목 수
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}
# ─────────────────────────────────────────

def get_today():
    today = datetime.today()
    if today.weekday() == 5: today -= timedelta(days=1)
    elif today.weekday() == 6: today -= timedelta(days=2)
    return today.strftime("%Y%m%d")

def fmt_amount(val):
    """거래대금 억 단위 변환"""
    ok = val / 100_000_000
    if ok >= 10000:
        return f"{ok/10000:.1f}조"
    return f"{ok:,.0f}억"

# ── 1. 네이버 금융 테마 목록 크롤링 ─────────────
def get_naver_themes():
    print("[1/4] 네이버 테마 목록 수집 중...")
    themes = {}
    try:
        # 테마 목록 페이지
        url = "https://finance.naver.com/sise/theme.naver"
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("table.type_1 tr")
        theme_links = []
        for row in rows:
            a = row.select_one("td.col_type1 a")
            if a and a.get("href"):
                theme_links.append({
                    "name": a.text.strip(),
                    "href": "https://finance.naver.com" + a["href"]
                })

        print(f"  테마 {len(theme_links)}개 발견")

        # 각 테마별 종목 수집
        for i, theme in enumerate(theme_links):
            try:
                time.sleep(0.3)
                res2 = requests.get(theme["href"], headers=HEADERS, timeout=10)
                soup2 = BeautifulSoup(res2.text, "html.parser")
                tickers = []
                for a in soup2.select("table.type_5 td.name a, table.type_2 td.name a"):
                    href = a.get("href", "")
                    m = re.search(r"code=(\d{6})", href)
                    if m:
                        tickers.append(m.group(1))
                if tickers:
                    themes[theme["name"]] = list(set(tickers))
                if (i+1) % 10 == 0:
                    print(f"  진행: {i+1}/{len(theme_links)}")
            except Exception:
                continue

        print(f"  종목 포함 테마: {len(themes)}개")
    except Exception as e:
        print(f"  네이버 테마 수집 실패: {e}")
        # 기본 테마 사전 (백업용)
        themes = {
            "AI반도체": ["000660", "005930", "042700", "240810", "054730"],
            "방산": ["012450", "047810", "064350", "079550", "272210"],
            "2차전지": ["006400", "051910", "096770", "247540", "373220"],
            "바이오": ["068270", "207940", "326030", "091990", "196170"],
            "자동차": ["005380", "000270", "012330", "204320", "018880"],
            "조선": ["009540", "010140", "042660", "329180", "100840"],
            "게임": ["036570", "251270", "263750", "112040", "293490"],
            "엔터": ["035900", "041510", "122870", "352820", "003230"],
        }
    return themes

# ── 2. pykrx 거래대금 상위 60 수집 ──────────────
def get_top60(today):
    print("[2/4] 거래대금 상위 60위 수집 중...")
    df = stock.get_market_ohlcv_by_ticker(today, market="ALL")

    # pykrx 버전에 따라 컬럼명이 다름 (한글 or 영어)
    cols = df.columns.tolist()
    if "거래대금" in cols:
        amount_col, close_col, open_col = "거래대금", "종가", "시가"
    else:
        amount_col, close_col, open_col = "TradingValue", "Close", "Open"

    df = df[df[amount_col] > 0].copy()
    df = df.sort_values(amount_col, ascending=False).head(TOP_N)

    result = []
    for ticker, row in df.iterrows():
        try:
            name   = stock.get_market_ticker_name(ticker)
            close  = float(row[close_col])
            open_  = float(row[open_col])
            chg    = round((close - open_) / open_ * 100, 2) if open_ > 0 else 0
            amount = int(row[amount_col])
            result.append({
                "ticker": ticker,
                "name":   name,
                "close":  close,
                "change": chg,
                "amount": amount,
                "amount_str": fmt_amount(amount)
            })
        except Exception:
            continue

    print(f"  {len(result)}개 종목 수집 완료")
    return result

# ── 3. 주도 테마 분석 ────────────────────────────
def analyze_themes(top60, themes):
    print("[3/4] 주도 테마 분석 중...")
    top60_tickers = {s["ticker"]: s for s in top60}

    theme_results = []
    for theme_name, ticker_list in themes.items():
        # 이 테마에서 TOP60 안에 있는 종목 찾기
        matched = []
        for ticker in ticker_list:
            if ticker in top60_tickers:
                s = top60_tickers[ticker]
                if s["change"] > 0:  # 상승 종목만
                    matched.append(s)

        if len(matched) >= MIN_THEME_CNT:
            # 거래대금 합산
            total_amount = sum(s["amount"] for s in matched)
            # 대장주: 상승률 * 거래대금 점수 → 가장 높은 종목
            for s in matched:
                s["score"] = s["change"] * (s["amount"] / 1_000_000_000)
            champion = max(matched, key=lambda x: x["score"])
            # 나머지는 거래대금 순 정렬
            others = sorted(
                [s for s in matched if s["ticker"] != champion["ticker"]],
                key=lambda x: -x["amount"]
            )
            theme_results.append({
                "theme":        theme_name,
                "total_amount": total_amount,
                "total_str":    fmt_amount(total_amount),
                "count":        len(matched),
                "champion":     champion,
                "stocks":       others
            })

    # 거래대금 합산 기준으로 테마 순위
    theme_results = sorted(theme_results, key=lambda x: -x["total_amount"])
    print(f"  주도 테마 {len(theme_results)}개 발견")
    return theme_results

# ── 4. 최종 저장 ─────────────────────────────────
def save(today, top60, themes):
    print("[4/4] 결과 저장 중...")

    total_amount     = sum(s["amount"] for s in top60)
    theme_amount     = sum(t["total_amount"] for t in themes)
    theme_ratio      = round(theme_amount / total_amount * 100, 1) if total_amount else 0
    non_theme_amount = total_amount - theme_amount

    # 날짜 포맷
    d = datetime.strptime(today, "%Y%m%d")
    date_str = d.strftime("%Y년 %m월 %d일 (%a)").replace(
        "Mon","월").replace("Tue","화").replace("Wed","수").replace(
        "Thu","목").replace("Fri","금")

    data = {
        "date":             date_str,
        "generated_at":     datetime.now().strftime("%H:%M"),
        "summary": {
            "total_amount":     total_amount,
            "total_str":        fmt_amount(total_amount),
            "theme_amount":     theme_amount,
            "theme_str":        fmt_amount(theme_amount),
            "theme_ratio":      theme_ratio,
            "non_theme_amount": non_theme_amount,
            "non_theme_str":    fmt_amount(non_theme_amount),
            "theme_count":      len(themes),
            "top60_count":      len(top60)
        },
        "themes": themes,
        "top60":  top60,
        "settings": {
            "top_n":         TOP_N,
            "min_theme_cnt": MIN_THEME_CNT
        }
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료!")
    print(f"  거래대금 TOP60 합산: {fmt_amount(total_amount)}")
    print(f"  주도 테마 합산:      {fmt_amount(theme_amount)} ({theme_ratio}%)")
    print(f"  주도 테마 수:        {len(themes)}개")
    print(f"\n→ dashboard.html 을 브라우저로 열어보세요!")

if __name__ == "__main__":
    print("=" * 50)
    print("  주도 테마 분석기 시작")
    print("=" * 50)
    today  = get_today()
    print(f"  기준일: {today}\n")
    themes = get_naver_themes()
    top60  = get_top60(today)
    result = analyze_themes(top60, themes)
    save(today, top60, result)
