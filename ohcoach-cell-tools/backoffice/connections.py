import os

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session


class OhcoachDataConnection:
    def __init__(self):
        load_dotenv()

        ID = os.getenv("DB_ID_ULTIMATE")
        PW = os.getenv("DB_PW_ULTIMATE")
        HOST = os.getenv("DB_HOST_ULTIMATE")
        SCHEME = os.getenv("DB_DATABASE_DEFAULT_SCHEMA_ULTIMATE")

        self.engine = create_engine(
            f"mysql+pymysql://{ID}:{PW}@{HOST}:3306/{SCHEME}?charset=utf8", encoding="utf-8"
        )
        metadata = MetaData()
        metadata.reflect(self.engine, only=["team"])
        self.base = automap_base(metadata=metadata)
        self.base.prepare()
        self.session = Session(bind=self.engine)

    @property
    def team(self) -> list[dict[str, str]]:
        team = self.base.classes.team
        query = self.session.query(team.idf_team, team.name, team.gender, team.group_age)
        team_result = self.session.execute(query)
        result = [
            {"value": f"{row[0]}", "label": f"{row[1]}_{row[2]}_{row[3]} (team_{row[0]})"}
            for row in team_result
        ]
        return result

    def get_cell_of_player(self, _idf_team: str) -> dict[str, str]:
        query = f"""
        select nickname, device_model, device_version, device_number from team_player where idf_team = {_idf_team}
        """
        team_player_result = self.session.execute(query)
        player_info = {f"{row[1]}-{row[2]}-{str(row[3])}": row[0] for row in team_player_result}
        return player_info
