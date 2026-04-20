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

# 업종명 통일 매핑
# 한국투자증권 API 업종명 → 우리가 쓸 업종명
SECTOR_MAP = {
    # 소분류(idx_bztp_scls_cd_name) 기준
    "반도체": "반도체",
    "전기,전자": "전기전자",
    "디지털컨텐츠": "게임/콘텐츠",
    "소프트웨어": "게임/콘텐츠",
    "운수장비": "자동차",
    "운수창고": "해운/항공",
    "의약품": "바이오/제약",
    "의료정밀": "바이오/제약",
    "화학": "화학",
    "철강금속": "철강",
    "기계": "기계/방산",
    "건설업": "건설",
    "금융업": "금융",
    "은행": "금융",
    "증권": "금융",
    "보험업": "금융",
    "통신업": "통신",
    "서비스업": "서비스",
    "음식료업": "음식료",
    "유통업": "유통",
    "전기가스업": "전기가스",
    # 표준산업분류(std_idst_clsf_cd_name) 기준
    "해상 운송업": "해운",
    "항공 운송업": "항공",
    "무기 및 총포탄 제조업": "방산",
    "항공기, 우주선 및 부품 제조업": "방산",
    "군사용 차량 제조업": "방산",
    "선박 및 보트 건조업": "조선",
    "일차전지 및 축전지 제조업": "2차전지",
    "기초 화학물질 제조업": "화학",
    "합성고무 및 플라스틱 물질 제조업": "화학",
    "의약품 제조업": "바이오/제약",
    "기초 의약물질 및 생물학적 제제 제조업": "바이오/제약",
    "반도체 제조업": "반도체",
    "특수 목적용 기계 제조업": "반도체장비",
    "소프트웨어 개발 및 공급업": "게임/콘텐츠",
    "자동차 제조업": "자동차",
    "자동차 부품 제조업": "자동차",
    "통신 및 방송 장비 제조업": "전기전자",
    "전자 부품 제조업": "전기전자",
    "원자력 발전업": "원전",
    "화력 발전업": "전기가스",
    "태양광 발전업": "신재생에너지",
    "풍력 발전업": "신재생에너지",
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
    print("[0/4] 토큰 발급 중...")
    res = requests.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={"grant_type": "client_credentials",
              "appkey": APP_KEY, "appsecret": APP_SECRET},
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
                headers=headers, params=params, timeout=15
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
    print(f"  {len(results)}개 수집 완료 (스팩 제외)")
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
        # 소분류 우선, 없으면 표준산업분류
        scls = out.get("idx_bztp_scls_cd_name", "").strip()
        std  = out.get("std_idst_clsf_cd_name", "").strip()

        # 매핑 테이블에서 업종명 찾기
        for key in [scls, std]:
            if key in SECTOR_MAP:
                return SECTOR_MAP[key]

        # 매핑 없으면 소분류 그대로 반환
        return scls if scls else std if std else "기타"
    except:
        return "기타"


def classify_top60(token, top60):
    print("[2/4] TOP60 업종 분류 중...")
    print(f"  {len(top60)}개 종목 조회 중...")
    for i, s in enumerate(top60):
        s["sector"] = get_sector(token, s["ticker"])
        time.sleep(0.2)
    print("  완료!")
    return top60


def analyze(top60):
    print("[3/4] 주도 업종 분석 중...")

    # 업종별 그룹화
    sector_map = {}
    for s in top60:
        sector = s.get("sector", "기타")
        if sector == "기타":
            continue
        if sector not in sector_map:
            sector_map[sector] = []
        sector_map[sector].append(s)

    theme_results = []
    for sector_name, stocks in sector_map.items():
        # 상승 종목만
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
        theme_results.append({
            "theme": sector_name,
            "total_amount": total,
            "total_str": fmt_amount(total),
            "count": len(rising),
            "champion": champ,
            "stocks": others
        })

    theme_results = sorted(theme_results, key=lambda x: -x["total_amount"])
    print(f"  주도 업종 {len(theme_results)}개 발견")
    return theme_results


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
    print(f"\n완료!")
    print(f"  TOP60: {fmt_amount(total)}")
    print(f"  주도 업종: {fmt_amount(tamt)} ({ratio}%) / {len(themes)}개")

    # TOP60 업종 현황 출력
    print(f"\n[TOP60 업종 현황]")
    sector_count = {}
    for s in top60:
        sec = s.get("sector","기타")
        sector_count[sec] = sector_count.get(sec, 0) + 1
    for sec, cnt in sorted(sector_count.items(), key=lambda x: -x[1]):
        print(f"  {sec}: {cnt}개")

    print(f"\n→ 웹사이트에서 확인하세요!")


if __name__ == "__main__":
    print("=" * 50)
    print("  주도 업종 분석기 v3 (한국투자증권 API)")
    print("=" * 50)
    today = get_today()
    print(f"  기준일: {today}\n")
    token  = get_token()
    top60  = get_top60(token)
    top60  = classify_top60(token, top60)
    themes = analyze(top60)
    save(today, top60, themes)
