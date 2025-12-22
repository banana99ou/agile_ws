import pandas as pd


def __read_file_data(file_path: str, mode: str):
    data = None
    with open(file_path, mode) as f:
        data = f.read()

    return data


def __get_df(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path, dtype=str)


# intermed generator test data
TEST_FILE_PATH = "tests/gp_im_parser/generators/sample_data/intermed_generator"
TEST_GP_FILE_PATH = f"{TEST_FILE_PATH}/CLBX-4B-42510_2.0_0_1660914714_0.gp"
TEST_GP_DATA = __read_file_data(file_path=TEST_GP_FILE_PATH, mode="rb")
TEST_IM_FILE_PATH = f"{TEST_FILE_PATH}/CLBX-4B-42510_2.0_0_1660914714_0.im"
TEST_IM_DATA = __read_file_data(file_path=TEST_IM_FILE_PATH, mode="rb")

TEST_GP_TO_RGP_CSV_FILE_PATH = f"{TEST_FILE_PATH}/CLBX-4B-42510_2.0_0_1660914714_0_1_rgp.csv"
TEST_GP_TO_RGP_DF = __get_df(file_path=TEST_GP_TO_RGP_CSV_FILE_PATH)
TEST_IM_TO_RIM_CSV_FILE_PATH = f"{TEST_FILE_PATH}/CLBX-4B-42510_2.0_0_1660914714_0_1_rim.csv"
TEST_IM_TO_RIM_DF = __get_df(file_path=TEST_IM_TO_RIM_CSV_FILE_PATH)

TEST_GP_TO_RGP_CSV_FILE_PATH_2 = f"{TEST_FILE_PATH}/CLBX-4B-42510_2.0_0_1660914714_0_2_rgp.csv"
TEST_GP_TO_RGP_DF_2 = __get_df(file_path=TEST_GP_TO_RGP_CSV_FILE_PATH_2)
TEST_IM_TO_RIM_CSV_FILE_PATH_2 = f"{TEST_FILE_PATH}/CLBX-4B-42510_2.0_0_1660914714_0_2_rim.csv"
TEST_IM_TO_RIM_DF_2 = __get_df(file_path=TEST_IM_TO_RIM_CSV_FILE_PATH_2)
