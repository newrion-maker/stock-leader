import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json, time, os

load_dotenv()

APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
BASE_URL = "https://openapi.koreainvestment.com:9443"

TOP_N = 60
MIN_THEME_CNT = 3

THEMES = {
    "반도체": [
        "005930","000660","042700","403870","058470",
        "039030","240810","357780","005290","067310",
        "036930","007660","102120","009150","018260",
    ],
    "방산/항공": [
        "012450","079550","064350","047810","272210",
        "010820","065450","105840","011760","003570",
    ],
    "조선": [
        "009540","010140","042660","329180","010620",
        "082740","077970","071970","014970","005430",
    ],
    "2차전지": [
        "373220","006400","096770","247540","003670",
        "066970","005070","278280","336570","093370",
        "450080","006110","011810","298040",
    ],
    "바이오/제약": [
        "207940","068270","196170","128940","000100",
        "028300","237690","091990","145020","041830",
        "011000","382150",
    ],
    "자동차": [
        "005380","000270","012330","204320","011210",
        "018880","015750","023810","007570",
    ],
    "게임": [
        "259960","036570","251270","293490","263750",
        "041140","112040","069080","123420","047820",
    ],
    "엔터": [
        "352820","041510","035900","122870","037270",
        "020120","041040","016360",
    ],
    "인터넷/플랫폼": [
        "035720","035420","377300","323410","067160",
        "041020",
    ],
    "은행/금융": [
        "105560","055550","086790","316140","024110",
        "138930","175330","012030",
    ],
    "보험": [
        "032830","000810","005830","000060","088350","001450",
    ],
    "철강/금속": [
        "005490","004020","010130","000670","016380",
        "053260","026940","008350","018470","006340",
        "001440","014160",
    ],
    "화학": [
        "051910","011170","011780","298050","009830",
        "001210",
    ],
    "정유": [
        "096770","010950","078930",
    ],
    "건설": [
        "028260","000720","006360","375500","294870",
        "047040",
    ],
    "원전": [
        "034020","130660","083650","051600","298040",
        "011930",
    ],
    "로봇": [
        "277810","454910","058610","214150",
    ],
    "통신": [
        "017670","030200","032640",
    ],
    "항공/여행": [
        "003490","020560","089590","039130","272450",
    ],
    "해운": [
        "011200","028670","005880","003280",
    ],
    "전선": [
        "001440","006340","038680","014940",
    ],
    "디스플레이": [
        "034220","088130","003720",
    ],
}

SPAC_KEYWORDS = ["스팩", "SPAC", "spac"]


def is_spac(name):
    return any(k in name for k in SPAC_KEYWORDS)


def get_today():
    today = datetime.today()
    if today.weekday() == 5:
        today -= timedelta(days=1)
    elif today.weekday() == 6:
        today -= timedelta(days=2)
    return today.strftime("%Y%m%d")


def fmt_amount(val):
    ok = val / 100_000_000
    if ok >= 10000:
        return str(round(ok / 10000, 1)) + "조"
    return format(int(ok), ',') + "억"


def get_token():
    print("[0/3] 토큰 발급 중...")
    res = requests.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET},
        timeout=10
    )
    token = res.json().get("access_token")
    if not token:
        raise Exception("토큰 발급 실패")
    print("  완료!")
    return token


def get_top60(token):
    print("[1/3] 거래대금 TOP60 수집 중...")
    results = []
    headers = {
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHPST01710000",
        "Content-Type": "application/json; charset=utf-8"
    }
    for market in ["0", "1"]:
        try:
            params = {
                "fid_cond_mrkt_div_code": "J",
                "fid_cond_scr_div_code": "20171",
                "fid_input_iscd": "0001" if market == "0" else "1001",
                "fid_div_cls_code": "0",
                "fid_blng_cls_code": market,
                "fid_trgt_cls_code": "111111111",
                "fid_trgt_exls_cls_code": "0000000000",
                "fid_input_price_1": "",
                "fid_input_price_2": "",
                "fid_vol_cnt": "",
                "fid_input_date_1": ""
            }
            res = requests.get(
                f"{BASE_URL}/uapi/domestic-stock/v1/ranking/quote-balance",
                headers=headers,
                params=params,
                timeout=15
            )
            for item in res.json().get("output", []):
                ticker = item.get("mksc_shrn_iscd", "")
                name = item.get("hts_kor_isnm", "")
                close = int(item.get("stck_prpr", "0").replace(",", ""))
                chg = float(item.get("prdy_ctrt", "0").replace(",", ""))
                amount = int(item.get("acml_tr_pbmn", "0").replace(",", ""))
                if ticker and amount > 0 and not is_spac(name):
                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "close": close,
                        "change": chg,
                        "amount": amount,
                        "amount_str": fmt_amount(amount),
                        "market": "KOSPI" if market == "0" else "KOSDAQ"
                    })
            time.sleep(0.3)
        except Exception as e:
            print(f"  오류: {e}")

    results = sorted(results, key=lambda x: -x["amount"])[:TOP_N]
    spac_excluded = sum(1 for r in results if is_spac(r["name"]))
    print(f"  {len(results)}개 수집 완료 (스팩 제외)")
    return results


def analyze(top60):
    print("[2/3] 주도 업종 분석 중...")
    top60_map = {s["ticker"]: s for s in top60}
    theme_results = []
    for theme_name, tickers in THEMES.items():
        matched = [top60_map[t] for t in tickers
                   if t in top60_map and top60_map[t]["change"] > 0]
        if len(matched) < MIN_THEME_CNT:
            continue
        total = sum(s["amount"] for s in matched)
        for s in matched:
            s["score"] = s["change"] * (s["amount"] / 1_000_000_000)
        champ = max(matched, key=lambda x: x["score"])
        others = sorted(
            [s for s in matched if s["ticker"] != champ["ticker"]],
            key=lambda x: -x["amount"]
        )
        theme_results.append({
            "theme": theme_name,
            "total_amount": total,
            "total_str": fmt_amount(total),
            "count": len(matched),
            "champion": champ,
            "stocks": others
        })
    theme_results = sorted(theme_results, key=lambda x: -x["total_amount"])
    print(f"  주도 업종 {len(theme_results)}개 발견")
    return theme_results


def save(today, top60, themes):
    print("[3/3] 저장 중...")
    total = sum(s["amount"] for s in top60)
    tamt = sum(t["total_amount"] for t in themes)
    ratio = round(tamt / total * 100, 1) if total else 0
    d = datetime.strptime(today, "%Y%m%d")
    dm = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
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
    print(f"\n완료!")
    print(f"  TOP60: {fmt_amount(total)}")
    print(f"  주도 업종: {fmt_amount(tamt)} ({ratio}%) / {len(themes)}개")
    print(f"\n→ 웹사이트에서 확인하세요!")


if __name__ == "__main__":
    print("=" * 50)
    print("  주도 업종 분석기 (한국투자증권 API)")
    print("=" * 50)
    today = get_today()
    print(f"  기준일: {today}\n")
    token = get_token()
    top60 = get_top60(token)
    themes = analyze(top60)
    save(today, top60, themes)
