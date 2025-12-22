#!/bin/bash

export ZIP_FILE="intermed_generator_ftg.zip"

cd ..

zip -r -q ${ZIP_FILE} \
            ohcoach_cell_tools/common/aws_s3_helper.py \
            ohcoach_cell_tools/common/logger.py \
            ohcoach_cell_tools/ftg_parser/messages/start_message.py \
            ohcoach_cell_tools/ftg_parser/messages/gps_message.py \
            ohcoach_cell_tools/ftg_parser/messages/imu_message.py \
            ohcoach_cell_tools/ftg_parser/messages/bs_message.py \
            ohcoach_cell_tools/ftg_parser/messages/end_message.py \
            ohcoach_cell_tools/ftg_parser/managers/gps_message_manager.py \
            ohcoach_cell_tools/ftg_parser/managers/imu_message_manager.py \
            ohcoach_cell_tools/ftg_parser/managers/bs_message_manager.py \
            ohcoach_cell_tools/ftg_parser/managers/start_message_manager.py \
            ohcoach_cell_tools/ftg_parser/managers/ftg_message_manager.py \
            ohcoach_cell_tools/ftg_parser/managers/end_message_manager.py \
            ohcoach_cell_tools/ftg_parser/ftg_parser.py \
            ohcoach_cell_tools/ftg_parser/utils/ftg_message_utils.py \
            ohcoach_cell_tools/publishers/intermed_publisher.py \
            ohcoach_cell_tools/publishers/raw_data_publisher.py \
            ohcoach_cell_tools/constants.py \
            ohcoach_cell_tools/service/lambda_function_intermed_generator_newcell.py

aws s3 cp ${ZIP_FILE} ${S3_BUCKET}

aws lambda update-function-configuration --function-name ${INTERMED_FUNCTION_FTG} --memory-size 2056 --timeout 300
aws lambda put-function-event-invoke-config --function-name ${INTERMED_FUNCTION_FTG} --maximum-retry-attempts 0
aws lambda update-function-code --function-name ${INTERMED_FUNCTION_FTG} --zip-file fileb://${ZIP_FILE}

rm -rf ${ZIP_FILE}
