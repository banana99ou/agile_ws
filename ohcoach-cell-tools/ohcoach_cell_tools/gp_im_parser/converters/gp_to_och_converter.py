from typing import Optional

import pandas as pd

from ohcoach_cell_tools.constants import HEADER_OCH
from ohcoach_cell_tools.gp_im_parser.messages.nmea_message import (
    NmeaMessage,
    NmeaMessageType,
    NmeaRMCMessage,
)
from ohcoach_cell_tools.gp_im_parser.messages.och_message import OchMessage
from ohcoach_cell_tools.gp_im_parser.utils.dataframe_utils import get_processed_dataframe


class GpToOchConverter:
    def convert(self, gp_data: bytes) -> pd.DataFrame:
        """
        :param gp_data: String body of gp file with NMEA format
        :return: The dataframe of och (ugp_df), converted from the gp data
        """
        content_lines = gp_data.splitlines()
        och_message_list = []
        for gp_message in content_lines:
            try:
                nmea_rmc_message = self.__parse_gp_message_to_nmea_rmc_message(
                    gp_message=gp_message.decode("utf-8")
                )
                if not nmea_rmc_message:
                    continue
                och_message = self.__parse_nmea_rmc_message_to_och_message(nmea_rmc_message)
                if och_message:
                    och_message_list.append(och_message)
            except (ValueError, IndexError):
                pass

        return self.__get_och_df(och_message_list)

    def __parse_gp_message_to_nmea_rmc_message(self, gp_message: str) -> Optional[NmeaRMCMessage]:
        nmea_message = NmeaMessage(gp_message=gp_message)

        nmea_rmc_message = NmeaRMCMessage(nmea_message=nmea_message.message)

        if not (
            nmea_message.type == NmeaMessageType.RMC
            and nmea_message.is_nmea_format()
            and nmea_rmc_message.is_valid()
        ):
            return None

        return nmea_rmc_message

    def __parse_nmea_rmc_message_to_och_message(
        self, nmea_rmc_message: NmeaRMCMessage
    ) -> Optional[list]:
        och_message = OchMessage(nmea_rmc_message=nmea_rmc_message)

        if not och_message.is_valid():
            return None

        return och_message.items

    def __get_och_df(self, och_message_list: list) -> pd.DataFrame:
        # Convert och_message_list to DataFrame
        och_df = pd.DataFrame(och_message_list, columns=HEADER_OCH)
        och_df = get_processed_dataframe(df=och_df)

        return och_df
