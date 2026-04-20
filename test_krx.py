import requests
import os
from dotenv import load_dotenv

load_dotenv()
KRX_API_KEY = os.getenv("KRX_API_KEY")
print(f"KRX API Key: {KRX_API_KEY[:10]}...")

# 1단계: OTP 발급
print("\n[1단계] OTP 발급 중...")
otp_url = "https://openapi.krx.co.kr/contents/COM/GenerateOTP.jspx"
otp_params = {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
    "name": "fileDown",
    "filetype": "json",
}
otp_headers = {"AUTH_KEY": KRX_API_KEY}

res1 = requests.get(otp_url, params=otp_params, headers=otp_headers, timeout=10)
print(f"OTP 응답 코드: {res1.status_code}")
print(f"OTP 값: {res1.text[:100]}")

if res1.status_code == 200:
    otp = res1.text.strip()

    # 2단계: 실제 데이터 요청
    print("\n[2단계] 데이터 요청 중...")
    data_url = "https://openapi.krx.co.kr/contents/COM/GetMenuData.cmd"
    data_params = {"code": otp}

    res2 = requests.post(data_url, params=data_params, timeout=15)
    print(f"데이터 응답 코드: {res2.status_code}")
    print(f"데이터 내용: {res2.text[:300]}")
