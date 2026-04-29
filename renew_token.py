"""
구글 시트 및 드라이브 접근 권한 토큰 재발급 스크립트 (renew_token.py)
Drawing/Stock 두 프로젝트가 공유 토큰 파일을 사용하므로 여기서 한 번만 재인증하면 됨.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# 공유 토큰/인증 파일 경로 (절대경로)
SHARED_TOKEN  = r'C:\Users\hankook\Desktop\google_shared_token.json'
CREDENTIALS   = r'C:\Users\hankook\Desktop\Automation_Drawing\credentials.json'

def renew_token():
    if not os.path.exists(CREDENTIALS):
        print("❌ 오류: credentials.json 파일이 없습니다.")
        return

    print("🔄 구글 로그인 창을 엽니다. 브라우저에서 권한을 허용해 주세요...")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
    creds = flow.run_local_server(port=0)

    # 공유 경로에 저장 — Drawing/Stock 모두 이 파일을 읽음
    with open(SHARED_TOKEN, 'w') as token:
        token.write(creds.to_json())

    print(f"✅ 새 토큰 저장 완료: {SHARED_TOKEN}")
    print("   Drawing/Stock 봇 재시작 불필요 — 다음 실행 시 자동 적용됩니다.")

if __name__ == '__main__':
    renew_token()