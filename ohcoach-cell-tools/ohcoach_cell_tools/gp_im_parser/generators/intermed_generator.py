from ohcoach_cell_tools.common.logger import Logger
from ohcoach_cell_tools.gp_im_parser.converters.gp_to_och_converter import GpToOchConverter
from ohcoach_cell_tools.gp_im_parser.imu_parser import ImuParser
from ohcoach_cell_tools.gp_im_parser.utils.cell_info_utils import CellInfo
from ohcoach_cell_tools.gp_im_parser.utils.gp_im_data_utils import (
    ImuData,
    ReadableGPSData,
    ReadableIMUData,
)


class IntermedGenerator:
    _logger = Logger("IntermedGenerator")

    def __init__(self, cell_info: CellInfo, gp_data: bytes, im_data: bytes):
        self.gp_data = gp_data
        self.im_data = im_data
        self._rgp_data_list = []
        self._rim_data_list = []
        self.cell_info = cell_info

    def run(self):
        try:
            self.gp_to_rgp()
            self.im_to_rim()
        except Exception as e:
            self._logger.error(f"Error from run() - {e}")

    def gp_to_rgp(self):
        gp_data = self.gp_data.encode() if type(self.gp_data) is str else self.gp_data
        gp_page_data = gp_data.split(b"start")

        for i, gp in enumerate(gp_page_data):
            gp_to_och_converter = GpToOchConverter()
            och_df = gp_to_och_converter.convert(gp)
            if och_df.empty:
                continue

            rgp_data = ReadableGPSData(df=och_df, postfix=f"_{i}.rgp")
            self._rgp_data_list.append(rgp_data)

    def im_to_rim(self):
        im_data = self.im_data.encode() if type(self.im_data) is str else self.im_data
        page_delimiter = b"BIAS"
        im_page_data = im_data.split(page_delimiter)

        cell_info = self.cell_info
        frequency = int(im_page_data[0][:10].split(b",")[0])

        for i, im_stream in enumerate(im_page_data):
            im_stream = page_delimiter + im_stream
            imu_data = ImuData(
                im_stream=im_stream,
                device_version=cell_info.device_version,
                firmware_version=cell_info.firmware_version,
                frequency=frequency,
            )

            imu_parser = ImuParser(imu_data=imu_data)
            im_df = imu_parser.run()
            if im_df.empty:
                continue

            rim_data = ReadableIMUData(df=im_df, postfix=f"_{i}.rim")
            self._rim_data_list.append(rim_data)

    @property
    def rgp_data_list(self) -> list:
        return self._rgp_data_list

    @property
    def rim_data_list(self) -> list:
        return self._rim_data_list
