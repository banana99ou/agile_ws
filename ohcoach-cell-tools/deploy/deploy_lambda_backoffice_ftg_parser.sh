#!/bin/bash

export ZIP_FILE="backoffice_ftg_parser.zip"

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
            ohcoach_cell_tools/ftg_parser/managers/end_message_manager.py \
            ohcoach_cell_tools/ftg_parser/managers/ftg_message_manager.py \
            ohcoach_cell_tools/ftg_parser/utils/ftg_message_utils.py \
            ohcoach_cell_tools/ftg_parser/converters/ftg_to_gp_converter.py \
            ohcoach_cell_tools/ftg_parser/converters/ftg_to_im_converter.py \
            ohcoach_cell_tools/ftg_parser/ftg_parser.py \
            ohcoach_cell_tools/publishers/backoffice_ftg_parser_publisher.py \
            ohcoach_cell_tools/constants.py \
            ohcoach_cell_tools/service/lambda_function_backoffice_ftg_parser.py \
            scripts/parse.py

aws s3 cp ${ZIP_FILE} ${S3_BUCKET}

aws lambda update-function-configuration --function-name ${BACKOFFICE_FRG_PARSER_FUNCTION} --memory-size 2056 --timeout 300
aws lambda put-function-event-invoke-config --function-name ${BACKOFFICE_FRG_PARSER_FUNCTION} --maximum-retry-attempts 0
aws lambda update-function-code --function-name ${BACKOFFICE_FRG_PARSER_FUNCTION} --zip-file fileb://${ZIP_FILE}

rm -rf ${ZIP_FILE}
