#!/bin/bash

# 변수 설정
LAMBDA_FUNCTION_NAME="update_ranking"
ZIP_FILE="lambda_function.zip"
PACKAGE_DIR="package"

echo "🚀 AWS Lambda 배포 자동화 시작..."

# 1️⃣ 기존 패키지 삭제 및 새 디렉토리 생성
echo "🧹 기존 패키지 삭제 및 새 디렉토리 생성..."
rm -rf $PACKAGE_DIR $ZIP_FILE
mkdir -p $PACKAGE_DIR

# 2️⃣ 필요한 라이브러리 설치
echo "📦 라이브러리 설치 중..."
pip3 install --target ./$PACKAGE_DIR pymysql python-dotenv

# 3️⃣ 패키지 및 Lambda 코드 압축 (올바른 ZIP 구조 유지)
echo "🗜️  패키지 압축 중..."
cd $PACKAGE_DIR
zip -r ../$ZIP_FILE .
cd ..

# ✅ lambda_function.py를 ZIP 루트에 추가 (중요!)
zip -g $ZIP_FILE lambda_function.py

# ✅ 루트의 .env 파일 포함 (만약 필요하다면)
if [ -f ../.env ]; then
    echo "📁 .env 파일 포함"
    zip -g $ZIP_FILE ../.env
fi

# 4️⃣ Lambda 코드 업로드
echo "☁️ Lambda 코드 업로드 중..."
aws lambda update-function-code --function-name $LAMBDA_FUNCTION_NAME --zip-file fileb://$ZIP_FILE

# 5️⃣ Lambda 실행 테스트
echo "🛠️  Lambda 실행 테스트..."
aws lambda invoke --function-name $LAMBDA_FUNCTION_NAME output.txt
cat output.txt

echo "✅ Lambda 배포 완료!"