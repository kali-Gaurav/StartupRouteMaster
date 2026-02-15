import scrapy
from scraper.items import TrainScheduleItem, StationItem
from bs4 import BeautifulSoup
import re


class TrainSpider(scrapy.Spider):
    name = "train_spider"
    allowed_domains = ["erail.in"]  # Example domain, adjust as needed
    start_urls = [
        "https://erail.in/train-search?from=NDLS&to=MMCT&date=2024-02-15"  # Example URL
    ]

    def parse(self, response):
        # This is a basic example; real scraping would depend on the site structure
        soup = BeautifulSoup(response.text, 'html.parser')

        # Example: Find train listings
        trains = soup.find_all('div', class_='train-result')  # Hypothetical class

        for train in trains:
            item = TrainScheduleItem()
            item['train_number'] = train.find('span', class_='train-number').text.strip()
            item['train_name'] = train.find('span', class_='train-name').text.strip()
            item['source_station'] = train.find('span', class_='source').text.strip()
            item['destination_station'] = train.find('span', class_='destination').text.strip()
            item['departure_time'] = train.find('span', class_='departure').text.strip()
            item['arrival_time'] = train.find('span', class_='arrival').text.strip()
            item['duration'] = train.find('span', class_='duration').text.strip()
            # Add more fields as needed
            yield item


class StationSpider(scrapy.Spider):
    name = "station_spider"
    allowed_domains = ["indianrail.gov.in"]  # Example
    start_urls = [
        "https://indianrail.gov.in/station-codes/"  # Hypothetical
    ]

    def parse(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        stations = soup.find_all('tr')  # Example

        for station in stations[1:]:  # Skip header
            cols = station.find_all('td')
            if len(cols) >= 4:
                item = StationItem()
                item['station_code'] = cols[0].text.strip()
                item['station_name'] = cols[1].text.strip()
                item['latitude'] = cols[2].text.strip() if cols[2].text else None
                item['longitude'] = cols[3].text.strip() if cols[3].text else None
                # Add more
                yield item