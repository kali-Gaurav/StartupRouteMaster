# Route Engine Evolution - Kafka Infrastructure

**Feature:** Corridor Safety Bus  
**Owner:** DAEDALUS (Infrastructure Lead)  
**Status:** 🔄 DESIGN COMPLETE  
**Date:** 2026-05-08

---

## Overview

This document defines the Kafka infrastructure required for the Corridor Safety Bus to stream safety events in real-time.

---

## Kafka Cluster Requirements

### Minimum Production Setup

| Component | Specification | Count | Purpose |
|-----------|---------------|-------|---------|
| Broker | AWS MSK m5.large | 3 | Message brokers |
| ZooKeeper | m5.large | 3 | Cluster coordination |
| Storage | 1TB SSD per broker | - | Message persistence |

### Cost Estimate

| Resource | Monthly Cost |
|----------|--------------|
| AWS MSK (3 m5.large brokers) | $200/month |
| Storage (3TB total) | $30/month |
| Data transfer | $20/month |
| **Total** | **$250/month** |

---

## Topic Configuration

### Topic: `corridor.safety.events`

```bash
# Create topic command
kafka-topics.sh --create \
  --bootstrap-server $BROKER_URL \
  --topic corridor.safety.events \
  --partitions 6 \
  --replication-factor 3 \
  --config retention.ms=604800000 \  # 7 days
  --config cleanup.policy=delete \
  --config min.insync.replicas=2
```

### Topic Configuration

| Property | Value | Description |
|----------|-------|-------------|
| partitions | 6 | Parallel consumers |
| replication-factor | 3 | High availability |
| retention.ms | 604800000 | 7 days |
| cleanup.policy | delete | Auto-cleanup |
| min.insync.replicas | 2 | Durability guarantee |
| flush.ms | 60000 | Flush every 60s |
| segment.bytes | 1073741824 | 1GB segments |

### Topic: `corridor.safety.commands`

```bash
kafka-topics.sh --create \
  --bootstrap-server $BROKER_URL \
  --topic corridor.safety.commands \
  --partitions 3 \
  --replication-factor 3 \
  --config retention.ms=86400000  # 1 day
```

---

## Producer Configuration

```python
# backend/services/routing/kafka_producer.py

from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import logging

logger = logging.getLogger(__name__)

class SafetyEventProducer:
    """Kafka producer for safety events"""
    
    def __init__(self, bootstrap_servers: str = None):
        self.bootstrap_servers = bootstrap_servers or get_kafka_servers()
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas
            retries=3,
            retry_backoff_ms=100,
            max_in_flight_requests_per_connection=1,  # Ensure ordering
            linger_ms=5,  # Small batching
            batch_size=16384,
            compression_type='gzip',
            security_protocol='SASL_SSL',
            sasl_mechanism='SCRAM-SHA-512',
            sasl_plain_username=get_kafka_username(),
            sasl_plain_password=get_kafka_password()
        )
    
    async def publish_safety_event(self, event: dict) -> bool:
        """Publish safety event to Kafka"""
        try:
            future = self.producer.send(
                'corridor.safety.events',
                key=f"{event['corridor']}-{event['event_id']}",
                value={
                    **event,
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'route_engine'
                }
            )
            
            # Wait for confirmation
            record_metadata = await asyncio.wrap_future(future)
            
            logger.info(
                f"Safety event published: {event['event_id']} "
                f"to partition {record_metadata.partition} "
                f"offset {record_metadata.offset}"
            )
            
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to publish safety event: {e}")
            return False
    
    async def publish_command(self, command: dict) -> bool:
        """Publish command to control topic"""
        try:
            future = self.producer.send(
                'corridor.safety.commands',
                key=command['command_type'],
                value={
                    **command,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            await asyncio.wrap_future(future)
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to publish command: {e}")
            return False
    
    def close(self):
        """Close producer"""
        self.producer.flush()
        self.producer.close()
```

---

## Consumer Configuration

```python
# backend/services/routing/kafka_consumer.py

from kafka import KafkaConsumer
from kafka.errors import KafkaError
import asyncio
import logging

logger = logging.getLogger(__name__)

class SafetyEventConsumer:
    """Kafka consumer for safety events"""
    
    def __init__(self, bootstrap_servers: str = None, group_id: str = None):
        self.bootstrap_servers = bootstrap_servers or get_kafka_servers()
        self.group_id = group_id or 'route-engine-safety-consumer'
        self.consumer = KafkaConsumer(
            'corridor.safety.events',
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='latest',  # Start from latest
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            max_poll_records=100,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
            security_protocol='SASL_SSL',
            sasl_mechanism='SCRAM-SHA-512',
            sasl_plain_username=get_kafka_username(),
            sasl_plain_password=get_kafka_password()
        )
    
    async def consume_events(self, callback):
        """Consume safety events and call callback"""
        logger.info(f"Starting consumer for group {self.group_id}")
        
        try:
            async for message in self._async_consume():
                await callback(message.value)
                
        except asyncio.CancelledError:
            logger.info("Consumer cancelled")
        except Exception as e:
            logger.error(f"Consumer error: {e}")
    
    async def _async_consume(self):
        """Async wrapper for consumer"""
        while True:
            # Poll with timeout
            records = self.consumer.poll(timeout_ms=1000)
            
            for topic_partition, messages in records.items():
                for message in messages:
                    yield message
    
    def close(self):
        """Close consumer"""
        self.consumer.close()
```

---

## Docker Compose for Local Development

```yaml
# docker-compose.kafka.yml

version: '3.8'

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
    volumes:
      - zookeeper_data:/var/lib/zookeeper/data

  kafka-1:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-1:9092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    volumes:
      - kafka_data_1:/var/lib/kafka/data

  kafka-2:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9093:9093"
    environment:
      KAFKA_BROKER_ID: 2
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-2:9093,PLAINTEXT_HOST://localhost:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    volumes:
      - kafka_data_2:/var/lib/kafka/data

  kafka-3:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9094:9094"
    environment:
      KAFKA_BROKER_ID: 3
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-3:9094,PLAINTEXT_HOST://localhost:9094
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    volumes:
      - kafka_data_3:/var/lib/kafka/data

  kafkacat:
    image: confluentinc/cp-kafkacat:7.5.0
    depends_on:
      - kafka-1
    entrypoint: sleep infinity

volumes:
  zookeeper_data:
  kafka_data_1:
  kafka_data_2:
  kafka_data_3:
```

### Usage

```bash
# Start Kafka cluster
docker-compose -f docker-compose.kafka.yml up -d

# Create topics
docker-compose -f docker-compose.kafka.yml exec kafka-1 kafka-topics.sh \
  --create --bootstrap-server kafka-1:9092 \
  --topic corridor.safety.events \
  --partitions 6 --replication-factor 1

# List topics
docker-compose -f docker-compose.kafka.yml exec kafka-1 kafka-topics.sh \
  --list --bootstrap-server kafka-1:9092

# Test publishing
docker-compose -f docker-compose.kafka.yml exec kafkacat \
  kafkacat -P -b kafka-1:9092 -t corridor.safety.events

# Test consuming
docker-compose -f docker-compose.kafka.yml exec kafkacat \
  kafkacat -C -b kafka-1:9092 -t corridor.safety.events
```

---

## AWS MSK Configuration

### Terraform Module

```hcl
# terraform/kafka/main.tf

module "msk_cluster" {
  source = "./modules/msk"
  
  cluster_name = "route-engine-safety"
  kafka_version = "2.8.1"
  
  broker_node_group = {
    instance_type   = "kafka.m5.large"
    client_subnets  = module.vpc.private_subnets
    storage_info = {
      volume_size = 1000  # 1TB
      volume_type = "gp3"
    }
    security_groups = [aws_security_group.msk.id]
    number_of_broker_nodes = 3
  }
  
  encryption_info = {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
    encryption_in_transit = {
      client_broker = "TLS"
      in_cluster    = true
    }
  }
  
  configuration_info = {
    server_properties = file("msk-server.properties")
    arn              = aws_msk_configuration.msk.arn
  }
  
  client_authentication = {
    sasl = {
      scram = true
    }
  }
  
  logging_info = {
    broker_logs = {
      cloudwatch_logs = {
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }
}

# msk-server.properties
auto.create.topics.enable=true
default.replication.factor=3
min.insync.replicas=2
log.retention.hours=168
zookeeper.connection.timeout.ms=6000
```

---

## Monitoring

### CloudWatch Metrics

| Metric | Description | Alert |
|--------|-------------|-------|
| kafka.cluster.BrokerTopicMetrics.MessagesInPerSec | Messages per second | > 10000 |
| kafka.server.BrokerTopicMetrics.TotalProduceRequestsPerSec | Produce requests | > 5000 |
| kafka.server.BrokerTopicMetrics.TotalFetchRequestsPerSec | Fetch requests | > 10000 |
| kafka.controller.KafkaController.ActiveControllerCount | Active controllers | != 1 |
| kafka.server.ReplicaManager.UnderReplicatedPartitions | Under-replicated | > 0 |

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Route Engine - Kafka Monitoring",
    "panels": [
      {
        "title": "Messages In Per Second",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(kafka_server_BrokerTopicMetrics_MessagesInPerSec[5m]))",
            "legendFormat": "Total"
          }
        ]
      },
      {
        "title": "Under Replicated Partitions",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(kafka_server_ReplicaManager_UnderReplicatedPartitions)",
            "legendFormat": "Under Replicated"
          }
        ]
      }
    ]
  }
}
```

---

## Security

### SASL/SCRAM Authentication

```python
# Create user for route engine
kafka-configs.sh --bootstrap-server $BROKER \
  --alter-config --entity-type users \
  --entity-name route-engine \
  --add-config 'SCRAM-SHA-512=[password=secret]'
```

### ACL Configuration

```bash
# Grant permissions to route-engine user
kafka-acls.sh --bootstrap-server $BROKER \
  --add --allow-principal User:route-engine \
  --operation Write --topic corridor.safety.events

kafka-acls.sh --bootstrap-server $BROKER \
  --add --allow-principal User:route-engine \
  --operation Read --group route-engine-safety-consumer
```

---

## Action Items

| ID | Action | Owner | Status |
|----|--------|-------|--------|
| KAF-01 | Create Kafka topic designs | DAEDALUS | ✅ DONE |
| KAF-02 | Write producer/consumer code | DAEDALUS | ✅ DONE |
| KAF-03 | Create Docker Compose for local dev | DAEDALUS | ✅ DONE |
| KAF-04 | Write Terraform for AWS MSK | DAEDALUS | 🔴 PENDING |
| KAF-05 | Configure monitoring dashboards | DAEDALUS | 🔴 PENDING |
| KAF-06 | Set up SASL authentication | DAEDALUS | 🔴 PENDING |
| KAF-07 | Test failover scenarios | DAEDALUS | 🔴 PENDING |

---

## Cost Summary

| Environment | Monthly Cost |
|-------------|--------------|
| Development (Local) | $0 (Docker) |
| Staging (3 brokers) | $100 |
| Production (3 brokers) | $250 |
| **Budgeted** | **$350/month** |

---

**Document Version:** 1.0  
**Next Review:** 2026-05-15