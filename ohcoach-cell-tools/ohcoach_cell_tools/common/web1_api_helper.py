import json
import os

import requests


class Web1ApiHelper:
    API_URL = os.getenv("ENV_WEB_V1_API_URL") or ""

    @classmethod
    def update_db_original_data_from_ftg(cls, ftg_key: str, gp_key: str, im_key: str):
        request_url = Web1ApiHelper.API_URL + "/upload/updateDbOriginalDataFromFtg.php"
        headers = {"Content-Type": "application/json"}
        data = {"integratedFilePath": ftg_key, "filePath": [gp_key, im_key]}

        response = requests.post(request_url, data=json.dumps(data), headers=headers)

        return (
            {
                "status": response.status_code,
                "content": response.content,
            }
            if response.status_code != 200
            else response.json()
        )
