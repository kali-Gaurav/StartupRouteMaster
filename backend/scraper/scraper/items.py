import scrapy


class TrainScheduleItem(scrapy.Item):
    train_number = scrapy.Field()
    train_name = scrapy.Field()
    source_station = scrapy.Field()
    destination_station = scrapy.Field()
    departure_time = scrapy.Field()
    arrival_time = scrapy.Field()
    duration = scrapy.Field()
    stops = scrapy.Field()  # List of dicts with station, arrival, departure
    classes_available = scrapy.Field()  # List of classes
    scraped_at = scrapy.Field()


class StationItem(scrapy.Item):
    station_code = scrapy.Field()
    station_name = scrapy.Field()
    latitude = scrapy.Field()
    longitude = scrapy.Field()
    state = scrapy.Field()
    zone = scrapy.Field()
    scraped_at = scrapy.Field()