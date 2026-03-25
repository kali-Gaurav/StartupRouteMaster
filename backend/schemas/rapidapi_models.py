from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime

class RapidApiBase(BaseModel):
    model_config = {
        "from_attributes": True,
        "json_encoders": {datetime: lambda dt: dt.isoformat()},
        "populate_by_name": True,
        "str_strip_whitespace": True,
        "use_enum_values": True,
    }

# --- Shared Models ---

class ScheduleDay(RapidApiBase):
    day_code: Optional[str] = Field(None, alias="dayCode")
    runs: Optional[bool] = None

class TrainStop(RapidApiBase):
    station_name: Optional[str] = Field(None, alias="stationName")
    station_code: Optional[str] = Field(None, alias="stationCode")
    route_number: Optional[int] = Field(None, alias="routeNumber")
    arrival_time: Optional[str] = Field(None, alias="arrivalTime")
    departure_time: Optional[str] = Field(None, alias="departureTime")
    day_of_journey: Optional[int] = Field(None, alias="dayOfJourney")
    distance: Optional[str] = Field(None, alias="distance")

# --- Specific Models ---

class TrainSchedule(RapidApiBase):
    train_number: Optional[str] = Field(None, alias="trainNumber")
    train_name: Optional[str] = Field(None, alias="trainName")
    runs_on: List[ScheduleDay] = Field(default_factory=list, alias="runsOn")
    stops: List[TrainStop] = Field(default_factory=list, alias="data")

class AvailabilityInfo(RapidApiBase):
    date: Optional[str] = None
    availability_status: Optional[str] = Field(None, alias="availabilityStatus")
    total_fare: Optional[Union[int, str]] = Field(None, alias="totalFare")

class SeatAvailability(RapidApiBase):
    train_number: Optional[str] = Field(None, alias="trainNumber")
    train_name: Optional[str] = Field(None, alias="trainName")
    quota: Optional[str] = None
    availability: List[AvailabilityInfo] = Field(default_factory=list, alias="data")

class Passenger(RapidApiBase):
    number: Optional[int] = None
    booking_status: Optional[str] = Field(None, alias="bookingStatus")
    current_status: Optional[str] = Field(None, alias="currentStatus")

class PNRStatus(RapidApiBase):
    pnr_number: Optional[str] = Field(None, alias="pnrNumber")
    train_number: Optional[str] = Field(None, alias="trainNumber")
    train_name: Optional[str] = Field(None, alias="trainName")
    from_station: Optional[str] = Field(None, alias="fromStation")
    to_station: Optional[str] = Field(None, alias="toStation")
    boarding_point: Optional[str] = Field(None, alias="boardingPoint")
    destination_station: Optional[str] = Field(None, alias="destinationStation")
    journey_date: Optional[str] = Field(None, alias="journeyDate")
    journey_class: Optional[str] = Field(None, alias="class")
    passengers: List[Passenger] = Field(default_factory=list, alias="passenger")
    chart_prepared: Optional[bool] = Field(None, alias="chartPrepared")

class TrainBetweenStation(RapidApiBase):
    train_name: Optional[str] = Field(None, alias="train_name")
    train_number: Optional[str] = Field(None, alias="train_number")
    source_station_name: Optional[str] = Field(None, alias="source_station_name")
    source_station_code: Optional[str] = Field(None, alias="source_station_code")
    destination_station_name: Optional[str] = Field(None, alias="destination_station_name")
    destination_station_code: Optional[str] = Field(None, alias="destination_station_code")
    arrival_time: Optional[str] = Field(None, alias="arrival_time")
    departure_time: Optional[str] = Field(None, alias="departure_time")
    duration: Optional[str] = None

class TrainsBetweenStations(RapidApiBase):
    trains: List[TrainBetweenStation] = Field(default_factory=list, alias="data")

class FareDetail(RapidApiBase):
    class_type: Optional[str] = Field(None, alias="classType")
    fare: Optional[float] = None

class Fare(RapidApiBase):
    train_number: Optional[str] = Field(None, alias="trainNumber")
    from_station: Optional[str] = Field(None, alias="fromStation")
    to_station: Optional[str] = Field(None, alias="toStation")
    fares: List[FareDetail] = Field(default_factory=list, alias="data")

# --- v1/v2/v3 Specifics ---

class LiveStatus(RapidApiBase):
    train_number: Optional[str] = Field(None, alias="train_number")
    current_station_name: Optional[str] = Field(None, alias="current_station_name")
    current_station_code: Optional[str] = Field(None, alias="current_station_code")
    at_station: Optional[bool] = Field(None, alias="at_station")
    distance_from_source: Optional[int] = Field(None, alias="distance_from_source")
    delay: Optional[int] = None
    status: Optional[str] = None
    last_updated: Optional[str] = Field(None, alias="last_updated")

class LiveStationTrain(RapidApiBase):
    train_number: Optional[str] = Field(None, alias="train_number")
    train_name: Optional[str] = Field(None, alias="train_name")
    departure_time: Optional[str] = Field(None, alias="departure_time")
    expected_platform: Optional[str] = Field(None, alias="expected_platform")
    delay_minutes: Optional[int] = Field(default=0, alias="delay_minutes")
    status_message: Optional[str] = Field(None, alias="status_message")

class LiveStation(RapidApiBase):
    station_code: Optional[str] = Field(None, alias="station_code")
    station_name: Optional[str] = Field(None, alias="station_name")
    timestamp: Optional[str] = None
    trains: List[LiveStationTrain] = Field(default_factory=list, alias="data")

class LiveTrainStation(RapidApiBase):
    station_name: Optional[str] = Field(None, alias="station_name")
    station_code: Optional[str] = Field(None, alias="station_code")
    arrival_time: Optional[str] = Field(None, alias="arrival_time")
    departure_time: Optional[str] = Field(None, alias="departure_time")
    delay: Optional[int] = None
    status: Optional[str] = None

class LiveTrainStatus(RapidApiBase):
    train_number: Optional[str] = Field(None, alias="train_number")
    current_station: Optional[str] = Field(None, alias="current_station")
    delay: Optional[int] = None
    status: Optional[Union[str, bool]] = None
    last_updated: Optional[str] = Field(None, alias="last_updated")
    stations: List[LiveTrainStation] = Field(default_factory=list, alias="data")

class PNRStatusDetail(PNRStatus):
    booking_date: Optional[str] = Field(None, alias="bookingDate")
    total_passengers: Optional[int] = Field(None, alias="totalPassengers")
    chart_status: Optional[str] = Field(None, alias="chartStatus")

class TrainScheduleV2(TrainSchedule):
    pass

class TrainBetweenStationV3(TrainBetweenStation):
    train_type: Optional[str] = Field(None, alias="train_type")
    classes: List[str] = Field(default_factory=list)

class TrainsBetweenStationsV3(RapidApiBase):
    trains: List[TrainBetweenStationV3] = Field(default_factory=list, alias="data")

class FareV2(Fare):
    base_fare_total: Optional[float] = Field(None, alias="baseFare")
    tax_total: Optional[float] = Field(None, alias="tax")

class SearchStationResult(RapidApiBase):
    station_code: Optional[str] = Field(None, alias="stationCode")
    station_name: Optional[str] = Field(None, alias="stationName")
    name: Optional[str] = None # Fallback for some APIs

class SearchStation(RapidApiBase):
    stations: List[SearchStationResult] = Field(default_factory=list, alias="data")

class SearchTrainResult(RapidApiBase):
    train_number: Optional[str] = Field(None, alias="trainNumber")
    train_name: Optional[str] = Field(None, alias="trainName")
    from_station_code: Optional[str] = Field(None, alias="fromStationCode")
    to_station_code: Optional[str] = Field(None, alias="toStationCode")

class SearchTrain(RapidApiBase):
    trains: List[SearchTrainResult] = Field(default_factory=list, alias="data")

class TrainClassResult(RapidApiBase):
    code: Optional[str] = None
    name: Optional[str] = None

class TrainClasses(RapidApiBase):
    classes: List[Union[TrainClassResult, str]] = Field(default_factory=list, alias="data")

class StationTrain(RapidApiBase):
    train_name: Optional[str] = Field(None, alias="train_name")
    train_number: Optional[str] = Field(None, alias="train_number")
    departure_time: Optional[str] = Field(None, alias="departure_time")
    arrival_time: Optional[str] = Field(None, alias="arrival_time")
    travel_time: Optional[str] = Field(None, alias="travel_time")
    from_station_code: Optional[str] = Field(None, alias="from_station_code")
    to_station_code: Optional[str] = Field(None, alias="to_station_code")

class TrainsByStation(RapidApiBase):
    trains: List[StationTrain] = Field(default_factory=list, alias="data")
    originating: List[StationTrain] = Field(default_factory=list)
    terminating: List[StationTrain] = Field(default_factory=list)
