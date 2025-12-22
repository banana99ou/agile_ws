from dataclasses import dataclass


class NmeaMessageType:
    RMC = "RMC"


class NmeaMessage:
    def __init__(self, gp_message: str):
        self.message = gp_message

    def is_nmea_format(self) -> bool:
        return self.message[0:3] == "$GP" or self.message[0:3] == "$GN"

    @property
    def type(self) -> str:
        """
        $GPRMC,085851.20,A,4543.37440,N,01604.42747,E,0.551,,050122,,,A*75 : gp_message
        RMC : message_type
        $315,299,100,G38 : gp_message
        5 : message_type
        """
        return self.message[: self.message.index(",")][3:6]


@dataclass(init=True)
class NmeaRMCMessage:
    """
    DATA_FORMAT = "$GN{},{},A,{},{},{},{},{:.3f},,{},,,A*{:02X}"
    """

    full_message: str
    header: str
    utc_timestamp: str
    active_or_void: str
    latitude_dms: str
    north_or_south: str
    longitude_dms: str
    east_or_west: str
    speed_knot: str
    utc_datestamp: str
    checksum: str
    type: str = "RMC"

    def __init__(self, nmea_message: str):
        __message = nmea_message.split(",")
        self.full_message = nmea_message
        self.header = __message[0]
        self.utc_timestamp = __message[1]
        self.active_or_void = __message[2]  # active=A, void=V
        self.latitude_dms = __message[3]
        self.north_or_south = __message[4]  # north=N, south=S for latitude
        self.longitude_dms = __message[5]
        self.east_or_west = __message[6]  # east=E, west=W for longitude
        self.speed_knot = __message[7]
        self.utc_datestamp = __message[9]
        self.checksum = __message[12][2:]

    def is_valid(self) -> bool:
        return (
            self.header is not None
            and self.header[0] == "$"
            and self.active_or_void == "A"
            and self.__is_valid_checksum()
        )

    def __is_valid_checksum(self) -> bool:
        check_msg = self.full_message[self.full_message.find("$") + 1 : self.full_message.find("*")]
        checksum = 0
        for i in range(len(check_msg)):
            checksum = checksum ^ ord(check_msg[i])

        return hex(checksum).upper()[2:] == self.checksum
