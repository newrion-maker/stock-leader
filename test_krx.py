import requests
import os
from dotenv import load_dotenv

load_dotenv()

KRX_API_KEY = os.getenv("KRX_API_KEY")

print(f"KRX API Key 확인: {KRX_API_KEY[:10]}...")

# 유가증권 종목기본정보 조회 테스트
url = "https://openapi.krx.co.kr/contents/COM/GenerateOTP.jspx"
params = {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
    "name": "fileDown",
    "filetype": "json",
}
headers = {
    "AUTH_KEY": KRX_API_KEY
}

print("KRX API 호출 중...")
try:
    res = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"응답 코드: {res.status_code}")
    print(f"응답 내용: {res.text[:200]}")
except Exception as e:
    print(f"오류: {e}")
