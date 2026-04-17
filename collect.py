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
    print("[0/4] 토큰 발급 중...")
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
    print("[1/4] 거래대금 TOP60 수집 중...")
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
                if ticker and amount > 0:
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
    print(f"  {len(results)}개 수집 완료")
    return results


def get_industry(token, ticker):
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
        for key in ["idx_bztp_scls_cd_name", "idx_bztp_mcls_cd_name", "std_idst_clsf_cd_name"]:
            v = out.get(key, "").strip()
            if v:
                return v
    except:
        pass
    return "기타"


def classify(token, top60):
    print("[2/4] 업종 분류 중...")
    print(f"  {len(top60)}개 종목 조회 (약 2~3분)")
    for i, s in enumerate(top60):
        s["industry"] = get_industry(token, s["ticker"])
        if (i + 1) % 10 == 0:
            print(f"  진행: {i + 1}/{len(top60)}")
        time.sleep(0.2)
    print("  완료!")
    return top60


def analyze(top60):
    print("[3/4] 주도 테마 분석 중...")
    ind_map = {}
    for s in top60:
        ind = s.get("industry", "기타")
        if ind == "기타":
            continue
        if ind not in ind_map:
            ind_map[ind] = []
        ind_map[ind].append(s)
    results = []
    for ind, stocks in ind_map.items():
        rising = [s for s in stocks if s["change"] > 0]
        if len(rising) < MIN_THEME_CNT:
            continue
        total = sum(s["amount"] for s in rising)
        for s in rising:
            s["score"] = s["change"] * (s["amount"] / 1_000_000_000)
        champ = max(rising, key=lambda x: x["score"])
        others = sorted(
            [s for s in rising if s["ticker"] != champ["ticker"]],
            key=lambda x: -x["amount"]
        )
        results.append({
            "theme": ind,
            "total_amount": total,
            "total_str": fmt_amount(total),
            "count": len(rising),
            "champion": champ,
            "stocks": others
        })
    results = sorted(results, key=lambda x: -x["total_amount"])
    print(f"  주도 테마 {len(results)}개 발견")
    return results


def save(today, top60, themes):
    print("[4/4] 저장 중...")
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
    print(f"  주도 테마: {fmt_amount(tamt)} ({ratio}%) / {len(themes)}개")
    print(f"\n→ 웹사이트에서 확인하세요!")


if __name__ == "__main__":
    print("=" * 50)
    print("  주도 테마 분석기 (한국투자증권 API)")
    print("=" * 50)
    today = get_today()
    print(f"  기준일: {today}\n")
    token = get_token()
    top60 = get_top60(token)
    top60 = classify(token, top60)
    themes = analyze(top60)
    save(today, top60, themes)
