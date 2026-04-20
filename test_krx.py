import requests
import os
from dotenv import load_dotenv

load_dotenv()
KRX_API_KEY = os.getenv("KRX_API_KEY")
print("KRX KEY 확인:", KRX_API_KEY[:10])

print("1단계 OTP 발급 중...")
res1 = requests.post(
    "https://openapi.krx.co.kr/contents/COM/GenerateOTP.jspx",
    data={"bld":"dbms/MDC/STAT/standard/MDCSTAT01901","name":"fileDown","filetype":"json"},
    headers={"AUTH_KEY": KRX_API_KEY},
    timeout=10
)
print("OTP 응답코드:", res1.status_code)
print("OTP 값:", res1.text[:100])

if res1.status_code == 200:
    otp = res1.text.strip()
    print("2단계 데이터 요청 중...")
    res2 = requests.post(
        "https://openapi.krx.co.kr/contents/COM/GetMenuData.cmd",
        data={"code": otp},
        timeout=15
    )
    print("데이터 응답코드:", res2.status_code)
    print("데이터 내용:", res2.text[:300])
else:
    print("OTP 발급 실패!")