from typing import Tuple

import pandas as pd

from ohcoach_cell_tools.ftg_parser.ftg_parser import FtgParser

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-ftg-726b2761368b41e588466ba130035a21#3b53f25dd3664116b6e992b4b8f5ee35


def run(ftg_file) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list]:
    try:
        ftg_parse_message = []
        for i, (start, rgp, rim, rbs, end, errors) in enumerate(FtgParser.parse(ftg_file)):
            ftg_parse_message.append(
                {"index": f"{i}", "start": f"{start}", "end": f"{end}", "errors": f"{errors}"}
            )
            return rgp, rim, rbs, ftg_parse_message

    except Exception as e:
        print(f"########## {ftg_file} * EXCEPTION: {e} ###########")
        raise e
    finally:
        FtgParser.parsing_errors.clear()
