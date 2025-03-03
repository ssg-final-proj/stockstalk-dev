#!/bin/bash

AWS_REGION="ap-northeast-2"
ROLE_ARN=$(aws iam get-role --role-name LambdaExecutionRole --query "Role.Arn" --output text)
FUNCTIONS=("verify_email" "verify_recipient_email" "update_ranking")

echo "🚀 Lambda 배포 시작..."

for FUNCTION in "${FUNCTIONS[@]}"; do
    ZIP_FILE="$FUNCTION.zip"
    echo "📦 $FUNCTION 압축 중..."
    zip -r $ZIP_FILE $FUNCTION.py > /dev/null 2>&1

    echo "🚀 $FUNCTION Lambda 함수 배포 중..."
    aws lambda create-function \
        --function-name $FUNCTION \
        --runtime python3.9 \
        --role $ROLE_ARN \
        --handler "$FUNCTION.lambda_handler" \
        --zip-file fileb://$ZIP_FILE \
        --timeout 10 \
        --memory-size 128 \
        --region $AWS_REGION \
        || aws lambda update-function-code --function-name $FUNCTION --zip-file fileb://$ZIP_FILE --region $AWS_REGION

    echo "✅ $FUNCTION 배포 완료!"
done

echo "🎉 모든 Lambda 배포 완료!"