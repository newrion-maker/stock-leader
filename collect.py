import os, json, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pykrx_openapi import KRXOpenAPI
import requests

# .env 파일 경로 명시
_env_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
    os.path.join(os.getcwd(), '.env'),
    'D:\\주도테마_분석기\\stock-leader\\.env',
]
for _p in _env_paths:
    if os.path.exists(_p):
        load_dotenv(dotenv_path=_p)
        break

KRX_API_KEY = os.getenv("KRX_API_KEY")
APP_KEY     = os.getenv("APP_KEY")
APP_SECRET  = os.getenv("APP_SECRET")
BASE_URL    = "https://openapi.koreainvestment.com:9443"

TOP_N         = 60
MIN_THEME_CNT = 3

SECTOR_MAP = {
    "반도체":          "반도체",
    "전기,전자":        "전기전자",
    "디지털컨텐츠":     "게임/콘텐츠",
    "소프트웨어":       "게임/콘텐츠",
    "운수장비":         "자동차",
    "운수창고":         "해운/항공",
    "의약품":           "바이오/제약",
    "의료정밀":         "바이오/제약",
    "화학":             "화학",
    "철강금속":         "철강",
    "기계":             "기계/방산",
    "건설업":           "건설",
    "금융업":           "금융",
    "은행":             "금융",
    "증권":             "금융",
    "보험업":           "금융",
    "통신업":           "통신",
    "서비스업":         "서비스",
    "음식료업":         "음식료",
    "유통업":           "유통",
    "전기가스업":       "전기가스",
    "해상 운송업":              "해운",
    "항공 운송업":              "항공",
    "무기 및 총포탄 제조업":     "방산",
    "항공기, 우주선 및 부품 제조업": "방산",
    "선박 및 보트 건조업":       "조선",
    "일차전지 및 축전지 제조업":  "2차전지",
    "반도체 제조업":             "반도체",
    "특수 목적용 기계 제조업":    "반도체장비",
    "소프트웨어 개발 및 공급업":  "게임/콘텐츠",
    "자동차 제조업":             "자동차",
    "자동차 부품 제조업":        "자동차",
    "통신 및 방송 장비 제조업":  "전기전자",
    "전자 부품 제조업":          "전기전자",
    "원자력 발전업":             "원전",
    "기초 의약물질 및 생물학적 제제 제조업": "바이오/제약",
    "의약품 제조업":             "바이오/제약",
}

SPAC_KEYWORDS = ["스팩", "SPAC", "spac"]

def is_spac(name):
    return any(k in name for k in SPAC_KEYWORDS)

def get_today():
    today = datetime.today()
    if today.weekday() == 5: today -= timedelta(days=1)
    elif today.weekday() == 6: today -= timedelta(days=2)
    return today.strftime("%Y%m%d")

def fmt_amount(val):
    ok = val / 100_000_000
    if ok >= 10000:
        return str(round(ok / 10000, 1)) + "조"
    return format(int(ok), ',') + "억"

def get_token():
    print("[0/4] 한국투자증권 토큰 발급 중...")
    res = requests.post(f"{BASE_URL}/oauth2/tokenP",
        json={"grant_type":"client_credentials","appkey":APP_KEY,"appsecret":APP_SECRET},
        timeout=10)
    token = res.json().get("access_token")
    if not token: raise Exception("토큰 발급 실패")
    print("  완료!")
    return token

def get_top60():
    print("[1/4] KRX API로 거래대금 TOP60 수집 중...")
    client = KRXOpenAPI(api_key=KRX_API_KEY)
    today = get_today()

    # 코스피 + 코스닥
    data1 = client.get_stock_daily_trade(bas_dd=today)
    data2 = client.get_kosdaq_stock_daily_trade(bas_dd=today)

    all_stocks = data1.get("OutBlock_1", []) + data2.get("OutBlock_1", [])

    results = []
    for item in all_stocks:
        name   = item.get("ISU_NM", "")
        ticker = str(item.get("ISU_CD", "")).zfill(6)
        close  = float(item.get("TDD_CLSPRC") or 0)
        open_  = float(item.get("TDD_OPNPRC") or 0)
        chg    = float(item.get("FLUC_RT") or 0)
        amount = float(item.get("ACC_TRDVAL") or 0)
        market = item.get("MKT_NM", "")

        if amount > 0 and not is_spac(name) and ticker:
            results.append({
                "ticker": ticker,
                "name": name,
                "close": close,
                "change": chg,
                "amount": int(amount),
                "amount_str": fmt_amount(amount),
                "market": market
            })

    results = sorted(results, key=lambda x: -x["amount"])[:TOP_N]
    print(f"  {len(results)}개 수집 완료")
    return results

def get_sector(token, ticker):
    headers = {
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "CTPF1002R",
        "Content-Type": "application/json; charset=utf-8"
    }
    try:
        res = requests.get(
            f"{BASE_URL}/uapi/domestic-stock/v1/quotations/search-stock-info",
            headers=headers,
            params={"PRDT_TYPE_CD": "300", "PDNO": ticker},
            timeout=10
        )
        out = res.json().get("output", {})
        scls = out.get("idx_bztp_scls_cd_name", "").strip()
        std  = out.get("std_idst_clsf_cd_name", "").strip()
        for key in [scls, std]:
            if key in SECTOR_MAP:
                return SECTOR_MAP[key]
        return scls if scls else std if std else "기타"
    except:
        return "기타"

def classify_top60(token, top60):
    print("[2/4] TOP60 업종 분류 중...")
    for i, s in enumerate(top60):
        s["sector"] = get_sector(token, s["ticker"])
        if (i+1) % 10 == 0:
            print(f"  진행: {i+1}/{len(top60)}")
        time.sleep(0.2)
    print("  완료!")
    return top60

def analyze(top60):
    print("[3/4] 주도 업종 분석 중...")
    sector_map = {}
    for s in top60:
        sector = s.get("sector", "기타")
        if sector == "기타": continue
        if sector not in sector_map:
            sector_map[sector] = []
        sector_map[sector].append(s)

    results = []
    for sector_name, stocks in sector_map.items():
        rising = [s for s in stocks if s["change"] > 0]
        if len(rising) < MIN_THEME_CNT: continue
        total = sum(s["amount"] for s in rising)
        for s in rising:
            s["score"] = s["change"] * (s["amount"] / 1_000_000_000)
        champ  = max(rising, key=lambda x: x["score"])
        others = sorted(
            [s for s in rising if s["ticker"] != champ["ticker"]],
            key=lambda x: -x["amount"]
        )
        results.append({
            "theme": sector_name,
            "total_amount": total,
            "total_str": fmt_amount(total),
            "count": len(rising),
            "champion": champ,
            "stocks": others
        })

    results = sorted(results, key=lambda x: -x["total_amount"])
    print(f"  주도 업종 {len(results)}개 발견")
    return results

def save(today, top60, themes):
    print("[4/4] 저장 중...")
    total = sum(s["amount"] for s in top60)
    tamt  = sum(t["total_amount"] for t in themes)
    ratio = round(tamt / total * 100, 1) if total else 0
    d  = datetime.strptime(today, "%Y%m%d")
    dm = {0:"월",1:"화",2:"수",3:"목",4:"금",5:"토",6:"일"}
    data = {
        "date": f"{d.year}년 {d.month:02d}월 {d.day:02d}일 ({dm[d.weekday()]})",
        "generated_at": datetime.now().strftime("%H:%M"),
        "summary": {
            "total_amount": total,
            "total_str": fmt_amount(total),
            "theme_amount": tamt,
            "theme_str": fmt_amount(tamt),
            "theme_ratio": ratio,
            "non_theme_amount": total - tamt,
            "non_theme_str": fmt_amount(total - tamt),
            "theme_count": len(themes),
            "top60_count": len(top60)
        },
        "themes": themes,
        "top60": top60,
        "settings": {"top_n": TOP_N, "min_theme_cnt": MIN_THEME_CNT}
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료!")
    print(f"  TOP60: {fmt_amount(total)}")
    print(f"  주도 업종: {fmt_amount(tamt)} ({ratio}%) / {len(themes)}개")
    print(f"\n  [주도 업종 목록]")
    for i, t in enumerate(themes):
        print(f"  {i+1}위 {t['theme']} {t['total_str']} ({t['count']}종목)")
        print(f"     👑 대장주: {t['champion']['name']} {t['champion']['change']}%")

if __name__ == "__main__":
    print("=" * 50)
    print("  주도 업종 분석기 v4 (KRX + 한국투자증권)")
    print("=" * 50)
    today = get_today()
    print(f"  기준일: {today}\n")
    token  = get_token()
    top60  = get_top60()
    top60  = classify_top60(token, top60)
    themes = analyze(top60)
    save(today, top60, themes)
