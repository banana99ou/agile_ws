#!/bin/bash

export ZIP_FILE="unzip_ftg.zip"

cd ..

zip -r -q ${ZIP_FILE} \
            ohcoach_cell_tools/common/aws_s3_helper.py \
            ohcoach_cell_tools/common/logger.py \
            ohcoach_cell_tools/service/lambda_function_unzip_ftg.py

aws s3 cp ${ZIP_FILE} ${S3_BUCKET}

aws lambda update-function-configuration --function-name ${UNZIP_FTG_FUNCTION} --memory-size 2056 --timeout 300
aws lambda put-function-event-invoke-config --function-name ${UNZIP_FTG_FUNCTION} --maximum-retry-attempts 0
aws lambda update-function-code --function-name ${UNZIP_FTG_FUNCTION} --zip-file fileb://${ZIP_FILE}

rm -rf ${ZIP_FILE}
