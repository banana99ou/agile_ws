#!/bin/bash

export ZIP_FILE="intermed_generator.zip"

cd ..

zip -r -q ${ZIP_FILE} \
            ohcoach_cell_tools/common/aws_s3_helper.py \
            ohcoach_cell_tools/common/logger.py \
            ohcoach_cell_tools/gp_im_parser/generators/intermed_generator.py \
            ohcoach_cell_tools/gp_im_parser/utils/cell_info_utils.py \
            ohcoach_cell_tools/gp_im_parser/utils/gp_im_data_utils.py \
            ohcoach_cell_tools/gp_im_parser/utils/dataframe_utils.py \
            ohcoach_cell_tools/gp_im_parser/messages/nmea_message.py \
            ohcoach_cell_tools/gp_im_parser/messages/och_message.py \
            ohcoach_cell_tools/gp_im_parser/converters/gp_to_och_converter.py \
            ohcoach_cell_tools/gp_im_parser/imu_parser.py \
            ohcoach_cell_tools/constants.py \
            ohcoach_cell_tools/service/lambda_function_intermed_generator.py

aws s3 cp ${ZIP_FILE} ${S3_BUCKET}

aws lambda update-function-configuration --function-name ${INTERMED_FUNCTION} --memory-size 2056 --timeout 300
aws lambda update-function-code --function-name ${INTERMED_FUNCTION} --zip-file fileb://${ZIP_FILE}

rm -rf ${ZIP_FILE}
