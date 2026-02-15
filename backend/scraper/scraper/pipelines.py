# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json
import kafka
from datetime import datetime


class KafkaPipeline:
    def __init__(self, kafka_bootstrap_servers, kafka_topic):
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.kafka_topic = kafka_topic
        self.producer = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            kafka_bootstrap_servers=crawler.settings.get('KAFKA_BOOTSTRAP_SERVERS'),
            kafka_topic=crawler.settings.get('KAFKA_TOPIC')
        )

    def open_spider(self, spider):
        self.producer = kafka.KafkaProducer(
            bootstrap_servers=self.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def close_spider(self, spider):
        if self.producer:
            self.producer.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        data = dict(adapter)
        data['scraped_at'] = datetime.utcnow().isoformat()
        self.producer.send(self.kafka_topic, data)
        return item


class ScraperPipeline:
    def process_item(self, item, spider):
        return item