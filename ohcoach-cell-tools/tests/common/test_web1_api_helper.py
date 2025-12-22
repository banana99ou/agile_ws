from unittest.mock import patch

from requests.models import Response

from ohcoach_cell_tools.common.web1_api_helper import Web1ApiHelper


class TestWeb1ApiHelper:
    # Given ftg_key, gp_key, im_key
    ftg_key = "2022/02/09/CLBX-4B-41570_4.6_0_1644214757_0.ftg"
    gp_key = "2022/02/09/CLBX-4B-41570_4.6_0_1644214757_0.gp"
    im_key = "2022/02/09/CLBX-4B-41570_4.6_0_1644214757_0.im"

    @patch("requests.Response.content")
    @patch("requests.post")
    def test_update_db_original_data_from_ftg_when_receive_fail_result_code(self, mock_post, _):
        response = Response()

        response.status_code = 409
        bad_content = b'{"status":409,"msg":"Doesn\\u0027t exist a row to update","data":null}'
        setattr(response, "content", bad_content)

        mock_post.return_value = response

        # When: call update_db_original_data_from_ftg with given keys
        actual_result = Web1ApiHelper.update_db_original_data_from_ftg(
            self.ftg_key, self.gp_key, self.im_key
        )

        # Then: the result should be contain status code
        assert mock_post.called_once()
        assert actual_result == {
            "status": 409,
            "content": b'{"status":409,"msg":"Doesn\\u0027t exist a row to update","data":null}',
        }

    @patch("requests.Response.content")
    @patch("requests.post")
    def test_update_db_original_data_from_ftg(self, mock_post, _):
        response = Response()

        response.status_code = 200
        content = b'{"status": 200,"msg":"2 files Success","data":null}'
        setattr(response, "content", content)

        mock_post.return_value = response

        # When: call update_db_original_data_from_ftg with given keys
        actual_result = Web1ApiHelper.update_db_original_data_from_ftg(
            self.ftg_key, self.gp_key, self.im_key
        )

        # Then: the result should be contain status code
        assert mock_post.called_once()
        assert actual_result == {"status": 200, "msg": "2 files Success", "data": None}
