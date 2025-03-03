#!/bin/bash

# 🏗️ 변수 설정
LAMBDA_FUNCTIONS=("update_ranking" "check_email_verification")
LAMBDA_FILES=("lambda_function.py" "check_email_verification.py")
ZIP_FILE="lambda_function.zip"
PACKAGE_DIR="package"

echo "🚀 AWS Lambda 배포 자동화 시작..."

# 1️⃣ 기존 패키지 삭제 및 새 디렉토리 생성
echo "🧹 기존 패키지 삭제 및 새 디렉토리 생성..."
rm -rf $PACKAGE_DIR $ZIP_FILE
mkdir -p $PACKAGE_DIR

# 2️⃣ 필요한 라이브러리 설치 (공통 종속성)
echo "📦 라이브러리 설치 중..."
pip3 install --target ./$PACKAGE_DIR pymysql python-dotenv boto3

# 3️⃣ 패키지 및 Lambda 코드 압축
echo "🗜️  패키지 압축 중..."
cd $PACKAGE_DIR
zip -r ../$ZIP_FILE . > /dev/null
cd ..

# ✅ 각 Lambda 함수별로 배포 진행
for i in "${!LAMBDA_FUNCTIONS[@]}"
do
    FUNCTION_NAME=${LAMBDA_FUNCTIONS[$i]}
    FUNCTION_FILE=${LAMBDA_FILES[$i]}

    echo "🚀 배포 중: $FUNCTION_NAME"

    # ✅ 특정 Lambda 코드 추가
    zip -g $ZIP_FILE "$FUNCTION_FILE"

    # ✅ Lambda 함수 존재 여부 확인
    aws lambda get-function --function-name $FUNCTION_NAME > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        # 기존 함수 업데이트
        echo "☁️  $FUNCTION_NAME 코드 업데이트 중..."
        aws lambda update-function-code --function-name $FUNCTION_NAME --zip-file fileb://$ZIP_FILE
    else
        # 새로운 함수 생성
        echo "✨ $FUNCTION_NAME 새로 생성 중..."
        aws lambda create-function \
            --function-name $FUNCTION_NAME \
            --runtime python3.9 \
            --role arn:aws:iam::707677861059:role/LambdaExecutionRole \
            --handler ${FUNCTION_FILE%.*}.lambda_handler \
            --timeout 30 \
            --memory-size 256 \
            --zip-file fileb://$ZIP_FILE
    fi

    # ✅ Lambda 실행 테스트
    echo "🛠️  $FUNCTION_NAME 실행 테스트..."
    aws lambda invoke --function-name $FUNCTION_NAME "output_$FUNCTION_NAME.txt" > /dev/null
    cat "output_$FUNCTION_NAME.txt"
done

echo "✅ 모든 Lambda 배포 완료!"