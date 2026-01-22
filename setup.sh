#!/bin/bash
# 가상환경 설정 스크립트

echo "가상환경 생성 중..."
python -m venv venv

echo "가상환경 활성화 중..."
source venv/Scripts/activate

echo "패키지 설치 중..."
pip install -r requirements.txt

echo "설정 완료!"
echo "서버 실행: python app.py"

