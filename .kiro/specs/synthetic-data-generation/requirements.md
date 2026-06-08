# Synthetic Data Generation Framework - Requirements

**Spec Version:** 1.0  
**Created:** 2026-05-08  
**Owner:** NOVA (ML Engineer)  
**Status:** Draft

---

## 1. Executive Summary

This document defines the requirements for the Synthetic Data Generation Framework, a critical component of the AI System that enables cost-free route generation without real-time API calls. The framework will generate realistic synthetic data for ML training, route generation, and system testing.

**Key Objectives:**
- Generate 1M+ synthetic train schedules for route generation
- Generate 10M+ synthetic availability records for ML training
- Generate 5M+ synthetic user behavior records for personalization
- Ensure statistical validity and distribution matching with real data
- Enable cost-free route generation (zero API cost)
- Support validation button for real-time API on demand

---

## 2. Background

### 2.1 Problem Statement

The current route generation system relies on real-time API calls to RapidAPI for train schedules and availability data. This creates several challenges:

1. **High Cost:** Each API call costs money, limiting scalability
2. **Rate Limiting:** API providers limit the number of requests
3. **Latency:** Real-time API calls add 500ms+ latency per request
4. **Availability:** System depends on external API availability
5. **Data Scarcity:** Limited historical data for ML training

### 2.2 Solution Overview

Build a Synthetic Data Generation Framework that:
- Generates realistic synthetic data matching real data distributions
- Enables route generation without real-time API calls
- Provides training data for ML models
- Supports validation button for real-time verification
- Reduces operational costs by 93%

---

## 3. Scope

### 3.1 In Scope

- Synthetic train schedule generation
- Synthetic fare data generation
- Synthetic availability data generation
- Synthetic user behavior generation
- Synthetic station information augmentation
- Data quality validation and testing
- Integration with route generation engine
- Validation button API integration

### 3.2 Out of Scope

- Real-time API integration (handled separately)
- Bus schedule generation (future work)
- Flight schedule generation (future work)
- External data source integration (future work)

---

## 4. Data Types and Specifications

### 4.1 Train Schedules

**Purpose:** Enable route generation without real-time API

**Data Volume:**
- Current Real Data: ~10,000 routes
- Synthetic Target: 1,000,000+ routes
- Total: 1,010,000+ routes

**Fields Required:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| train_number | String | Unique train identifier | "12001" |
| train_name | String | Train name | "BSP NDLS EXP" |
| from_station | String | Origin station code | "NDLS" |
| to_station | String | Destination station code | "BCT" |
| departure_time | Time | Departure time | "06:00" |
| arrival_time | Time | Arrival time | "14:30" |
| duration | Duration | Total journey time | "8h 30m" |
| days_of_week | Array | Operating days | ["Mon", "Wed", "Fri"] |
| train_type | Enum | Category of train | "Express", "Superfast" |
| classes | Array | Available classes | ["SL", "3A", "2A", "1A"] |
| base_fare | Decimal | Base fare multiplier | 1.0 |
| distance | Integer | Distance in km | 1400 |

**Distribution Requirements:**

| Parameter | Real Data | Synthetic Target | Tolerance |
|-----------|-----------|------------------|-----------|
| Train Types | 60% Express, 30% Superfast, 10% Rajdhani | Same | ±5% |
| Class Distribution | 50% SL, 30% 3A, 15% 2A, 5% 1A | Same | ±5% |
| Duration Range | 2h - 48h | Same | ±10% |
| Distance Range | 50km - 5000km | Same | ±10% |

### 4.2 Fare Data

**Purpose:** ML training for fare prediction and pricing optimization

**Data Volume:**
- Current Real Data: 500,000 records
- Synthetic Target: 2,000,000+ records
- Total: 2,500,000+ records

**Fields Required:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| train_number | String | Train identifier | "12001" |
| from_station | String | Origin station code | "NDLS" |
| to_station | String | Destination station code | "BCT" |
| travel_class | Enum | Coach class | "SL", "3A", "2A", "1A" |
| base_fare | Decimal | Base fare in INR | 500.0 |
| dynamic_factor | Decimal | Demand multiplier | 1.2 |
| final_fare | Decimal | Calculated fare | 600.0 |
| booking_class | Enum | Booking type | "GN", "TQ", "PQ" |
| availability | Integer | Available seats | 25 |
| booking_date | Date | Date of booking | "2026-05-08" |
| travel_date | Date | Date of travel | "2026-05-15" |
| days_before_travel | Integer | Advance booking days | 7 |

**Distribution Requirements:**

| Parameter | Real Data | Synthetic Target | Tolerance |
|-----------|-----------|------------------|-----------|
| Base Fare Range | ₹100 - ₹5000 | Same | ±10% |
| Dynamic Factor | 0.8 - 2.5 | Same | ±10% |
| Availability | 0 - 100 | Same | ±15% |
| Advance Booking | 0 - 120 days | Same | ±10% |

### 4.3 Availability Data

**Purpose:** ML training for availability prediction (CAT model)

**Data Volume:**
- Current Real Data: 0 records
- Synthetic Target: 10,000,000+ records
- Total: 10,000,000+ records

**Fields Required:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| train_number | String | Train identifier | "12001" |
| from_station | String | Origin station code | "NDLS" |
| to_station | String | Destination station code | "BCT" |
| travel_date | Date | Date of travel | "2026-05-15" |
| travel_class | Enum | Coach class | "SL", "3A", "2A", "1A" |
| availability | Integer | Available seats | 25 |
| waiting_list | Integer | Waiting list count | 0 |
| confirmation_probability | Decimal | ML prediction | 0.85 |
| festival_factor | Decimal | Festival multiplier | 1.5 |
| weather_factor | Decimal | Weather impact | 1.0 |
| event_factor | Decimal | Event impact | 1.2 |
| seasonal_factor | Decimal | Season multiplier | 1.1 |
| demand_score | Decimal | Calculated demand | 0.75 |

**Distribution Requirements:**

| Parameter | Target | Tolerance |
|-----------|--------|-----------|
| Availability = 0 | 20% | ±5% |
| Availability < 10 | 30% | ±5% |
| Availability 10-50 | 35% | ±5% |
| Availability > 50 | 15% | ±5% |
| Waiting List > 0 | 25% | ±5% |

### 4.4 User Behavior Data

**Purpose:** Personalization and Journey DNA

**Data Volume:**
- Current Real Data: 50,000 users
- Synthetic Target: 5,000,000+ records
- Total: 5,050,000+ records

**Fields Required:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| user_id | UUID | Unique user identifier | "550e8400-e29b..." |
| session_id | UUID | Session identifier | "550e8400-e29b..." |
| search_timestamp | DateTime | When search occurred | "2026-05-08T10:30:00" |
| from_station | String | Origin station code | "NDLS" |
| to_station | String | Destination station code | "BCT" |
| travel_date | Date | Date of travel | "2026-05-15" |
| travel_class_preference | Enum | Preferred class | "3A" |
| time_preference | Enum | Time preference | "Morning", "Afternoon", "Evening" |
| train_type_preference | Enum | Train type preference | "Superfast" |
| price_sensitivity | Decimal | 0-1 scale | 0.7 |
| transfer_tolerance | Integer | Max transfers | 2 |
| search_results_count | Integer | Routes shown | 15 |
| clicked_routes | Array | Routes clicked | ["route-1", "route-3"] |
| booked_route | String |最终预订路线 | "route-1" |
| booking_completed | Boolean | Whether booked | true |
| time_to_booking | Duration | Time to book | "15m" |
| device_type | Enum | Mobile, Desktop, Tablet | "Mobile" |
| platform | Enum | iOS, Android, Web | "Android" |

**Distribution Requirements:**

| Parameter | Target | Tolerance |
|-----------|--------|-----------|
| Mobile Users | 70% | ±5% |
| Desktop Users | 25% | ±5% |
| Tablet Users | 5% | ±5% |
| Booking Completion | 15% | ±5% |
| Average Time to Book | 15 minutes | ±20% |
| Class Preference SL | 45% | ±5% |
| Class Preference 3A | 35% | ±5% |
| Class Preference 2A | 15% | ±5% |
| Class Preference 1A | 5% | ±5% |

### 4.5 Station Information

**Purpose:** Route generation and graph building

**Data Volume:**
- Current Real Data: 8,500 stations
- Synthetic Target: 8,500 stations (augmented)
- Total: 8,500 stations

**Fields Required:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| station_code | String | Unique code | "NDLS" |
| station_name | String | Full name | "New Delhi" |
| zone | String | Railway zone | "NR" |
| state | String | State | "Delhi" |
| city | String | City | "New Delhi" |
| latitude | Decimal | GPS latitude | 28.6421 |
| longitude | Decimal | GPS longitude | 77.2195 |
| elevation | Integer | Elevation in meters | 216 |
| station_type | Enum | Category | "NSG-1", "NSG-2", "NSG-3" |
| platforms | Integer | Number of platforms | 16 |
| amenities | Array | Available amenities | ["WiFi", "Food", "AC"] |
| connectivity_score | Decimal | 0-1 scale | 0.9 |
| hub_score | Decimal | 0-1 scale | 0.95 |

---

## 5. Functional Requirements

### 5.1 Data Generation Engine

**FR-DG-001:** Generate Train Schedules
- **Description:** Generate synthetic train schedules matching real data distributions
- **Input:** Real data samples, distribution parameters
- **Output:** 1M+ synthetic train schedule records
- **Validation:** KS test, chi-square test for distribution matching

**FR-DG-002:** Generate Fare Data
- **Description:** Generate synthetic fare data with dynamic pricing factors
- **Input:** Train schedules, historical fare patterns
- **Output:** 2M+ synthetic fare records
- **Validation:** Compare with real fare distributions

**FR-DG-003:** Generate Availability Data
- **Description:** Generate synthetic availability data with contextual factors
- **Input:** Train schedules, event calendar, weather data
- **Output:** 10M+ synthetic availability records
- **Validation:** Check for realistic patterns and correlations

**FR-DG-004:** Generate User Behavior Data
- **Description:** Generate synthetic user behavior for personalization training
- **Input:** Real user behavior samples, persona definitions
- **Output:** 5M+ synthetic user behavior records
- **Validation:** Compare session patterns, conversion rates

### 5.2 Data Quality Framework

**FR-DQ-001:** Distribution Validation
- **Description:** Validate synthetic data distributions match real data
- **Methods:** Kolmogorov-Smirnov test, chi-square test, KL divergence
- **Threshold:** >95% similarity required

**FR-DQ-002:** Statistical Validity
- **Description:** Ensure synthetic data passes statistical tests
- **Tests:** Hypothesis tests, correlation analysis, outlier detection
- **Threshold:** >99% statistical validity

**FR-DQ-003:** Realism Scoring
- **Description:** Score synthetic data for realism
- **Method:** Human evaluation + automated checks
- **Threshold:** >90% realism score

**FR-DQ-004:** Training Performance
- **Description:** Validate synthetic data for ML training
- **Method:** Train models on synthetic data, evaluate on real data
- **Threshold:** >85% model accuracy

### 5.3 Storage and Retrieval

**FR-SR-001:** Feature Store Integration
- **Description:** Store synthetic data in feature store for ML training
- **Integration:** Redis, PostgreSQL, or dedicated feature store
- **Format:** Standardized feature vectors

**FR-SR-002:** Route Graph Storage
- **Description:** Store synthetic train schedules in route graph format
- **Structure:** Graph database or adjacency list
- **Access:** O(1) station lookup, O(n) route generation

**FR-SR-003:** Data Partitioning
- **Description:** Partition synthetic data by time, region, and type
- **Strategy:** Time-based for availability, region-based for routes
- **Benefits:** Faster queries, easier updates

### 5.4 Integration Requirements

**FR-INT-001:** Route Engine Integration
- **Description:** Integrate synthetic data with route generation engine
- **Method:** Replace real-time API calls with synthetic data queries
- **Fallback:** Real-time API for validation button

**FR-INT-002:** ML Pipeline Integration
- **Description:** Feed synthetic data into ML training pipeline
- **Method:** Feature store integration, batch training
- **Validation:** Model performance metrics

**FR-INT-003:** Validation Button Integration
- **Description:** Enable real-time API validation for synthetic routes
- **Method:** API endpoint for validation requests
- **Cost:** Pay-per-use, user-triggered

---

## 6. Non-Functional Requirements

### 6.1 Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data Generation Speed | 10,000 records/second | Throughput test |
| Query Latency (Route) | <100ms | P95 latency |
| Query Latency (Availability) | <50ms | P95 latency |
| Storage Size | <100GB | Total storage |
| Generation Time (Full Dataset) | <4 hours | End-to-end |

### 6.2 Scalability Requirements

- **Horizontal Scaling:** Support 10x data volume increase
- **Concurrent Users:** Support 1000+ concurrent users
- **Data Growth:** Handle 10M+ new records/month
- **Geographic Scaling:** Support all Indian railway zones

### 6.3 Availability Requirements

- **System Uptime:** 99.9%
- **Data Freshness:** Daily updates for synthetic data
- **Recovery Time:** <1 hour for data recovery
- **Backup:** Daily backups with 30-day retention

### 6.4 Security Requirements

- **Data Privacy:** No real user data in synthetic generation
- **Access Control:** Role-based access to synthetic data
- **Audit Logging:** Log all data generation and access
- **Compliance:** GDPR-compliant synthetic data

### 6.5 Quality Requirements

- **Distribution Matching:** >95% KL divergence similarity
- **Statistical Validity:** >99% hypothesis test pass rate
- **Realism Score:** >90% human evaluation score
- **Training Performance:** >85% ML model accuracy

---

## 7. Data Generation Techniques

### 7.1 Statistical Distribution Matching

**Technique:** Analyze real data distributions and generate synthetic data with matching parameters

**Implementation:**
1. Extract distribution parameters from real data
2. Fit statistical distributions (normal, exponential, etc.)
3. Generate synthetic samples from fitted distributions
4. Validate with statistical tests

**Tools:**
- Python: scipy.stats, numpy
- Tests: KS test, chi-square test, Anderson-Darling test

### 7.2 Generative Models

**Technique:** Train GANs or VAEs on real data for realistic generation

**Implementation:**
1. Preprocess real data (normalization, encoding)
2. Train GAN/VAE model
3. Generate new samples from learned distribution
4. Validate generated samples

**Models:**
- GAN: StyleGAN, DCGAN for images; TabularGAN for structured data
- VAE: Standard VAE, β-VAE for controlled generation

**Use Cases:**
- User behavior patterns (complex, non-linear)
- Availability sequences (temporal patterns)
- Fare dynamics (market simulation)

### 7.3 Rule-Based Generation

**Technique:** Define domain rules and generate data following rules with controlled randomness

**Implementation:**
1. Define rules based on domain knowledge
2. Add controlled randomness within rule bounds
3. Validate against business logic
4. Iterate for coverage

**Examples:**
- Train schedules: Based on real timetable patterns
- Fare calculation: Based on distance and class
- Operating days: Based on train categories

### 7.4 Data Augmentation

**Technique:** Transform existing data to create variations

**Implementation:**
1. Apply transformations (noise addition, scaling, rotation)
2. Validate transformed data quality
3. Add to synthetic dataset

**Transformations:**
- Add Gaussian noise to numerical features
- Swap similar categories
- Time shifting for temporal data
- Feature crossing for combinations

---

## 8. Quality Metrics Framework

### 8.1 Distribution Similarity Metrics

| Metric | Description | Target | Frequency |
|--------|-------------|--------|-----------|
| KL Divergence | Measure distribution difference | <0.05 | Per generation |
| JS Divergence | Symmetric KL divergence | <0.05 | Per generation |
| Earth Mover's Distance | Wasserstein distance | <0.1 | Per generation |
| Kolmogorov-Smirnov | Distribution comparison | p-value > 0.05 | Per generation |

### 8.2 Statistical Validity Metrics

| Metric | Description | Target | Frequency |
|--------|-------------|--------|-----------|
| Hypothesis Test Pass Rate | % tests passing | >99% | Per generation |
| Correlation Preservation | Feature correlations | >0.95 | Per generation |
| Outlier Ratio | % outliers in synthetic | <5% | Per generation |
| Missing Value Ratio | % missing values | <1% | Per generation |

### 8.3 Realism Metrics

| Metric | Description | Target | Frequency |
|--------|-------------|--------|-----------|
| Human Evaluation Score | Human rating of realism | >90% | Weekly |
| Expert Review Score | Domain expert rating | >90% | Weekly |
| Anomaly Detection Score | % anomalies detected | <5% | Per generation |
| Domain Expert Validation | Expert approval rate | >95% | Monthly |

### 8.4 Training Performance Metrics

| Metric | Description | Target | Frequency |
|--------|-------------|--------|-----------|
| Model Accuracy | ML model accuracy on real data | >85% | Per training run |
| Model F1 Score | ML model F1 score | >0.85 | Per training run |
| Training Convergence | Epochs to convergence | <100 | Per training run |
| Generalization Gap | Train/real data performance gap | <5% | Per training run |

---

## 9. Integration Points

### 9.1 Route Generation Engine

**Interface:** Synthetic Data API

**Endpoints:**
```
GET /synthetic/routes?from={station}&to={station}&date={date}
GET /synthetic/schedules?train={train_number}
GET /synthetic/connections?from={station}&transfers={max}
```

**Data Format:** JSON response matching route engine requirements

### 9.2 ML Training Pipeline

**Interface:** Feature Store API

**Integration:**
- Store synthetic features in feature store
- Retrieve for batch training
- Track feature lineage

**Format:** Standardized feature vectors (numpy arrays, pandas DataFrames)

### 9.3 Validation Button

**Interface:** Validation API

**Endpoints:**
```
POST /validate/routes
Body: { routes: [route_ids], validate_availability: true }
Response: { validated_routes: [...], api_calls: 5, cost: 0.05 }
```

**Cost Model:** Pay-per-use based on API calls

---

## 10. Constraints and Assumptions

### 10.1 Constraints

- **Data Privacy:** Cannot use real user data for synthetic generation
- **Regulatory:** Must comply with data protection regulations
- **Cost:** Total generation cost <$100/month
- **Time:** Full dataset generation <4 hours
- **Storage:** Total storage <100GB

### 10.2 Assumptions

- Real data distributions are stable over time
- Synthetic data quality can be validated statistically
- ML models can learn from synthetic data
- Validation button will be used sparingly
- Bus/flight data will be added in future phases

---

## 11. Acceptance Criteria

### 11.1 Functional Acceptance

- [ ] Generate 1M+ synthetic train schedules
- [ ] Generate 2M+ synthetic fare records
- [ ] Generate 10M+ synthetic availability records
- [ ] Generate 5M+ synthetic user behavior records
- [ ] All distributions match real data (>95% similarity)
- [ ] Route generation works without real-time API
- [ ] Validation button triggers real-time API calls

### 11.2 Non-Functional Acceptance

- [ ] Data generation speed >10,000 records/second
- [ ] Query latency <100ms for route generation
- [ ] System uptime >99.9%
- [ ] Storage <100GB
- [ ] Generation time <4 hours

### 11.3 Quality Acceptance

- [ ] Distribution similarity >95%
- [ ] Statistical validity >99%
- [ ] Realism score >90%
- [ ] Training performance >85% accuracy

---

## 12. Dependencies

### 12.1 External Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Real Data Access | Access to real train schedules | ✅ Ready |
| Real Data Access | Access to historical fares | ✅ Ready |
| Real Data Access | Access to booking patterns | ✅ Ready |
| Feature Store | Redis or dedicated feature store | 🔲 Future |

### 12.2 Internal Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Route Engine | Route generation engine | ✅ Complete |
| ML Pipeline | ML training infrastructure | 🔲 Future |
| Validation API | Real-time validation endpoint | 🔲 Future |

---

## 13. Risks and Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Synthetic data quality insufficient | High | Medium | Rigorous validation, iterative improvement |
| Distribution drift over time | Medium | High | Regular re-calibration with real data |
| ML model not generalizing | High | Medium | Domain adaptation, transfer learning |
| Storage costs too high | Medium | Low | Compression, tiered storage |
| Validation button overused | Medium | Medium | User education, cost display |

---

## 14. Glossary

| Term | Definition |
|------|------------|
| Synthetic Data | Artificially generated data that mimics real data characteristics |
| Distribution Matching | Ensuring synthetic data has similar statistical properties to real data |
| KL Divergence | Kullback-Leibler divergence, a measure of difference between distributions |
| GAN | Generative Adversarial Network, a type of ML model for data generation |
| VAE | Variational Autoencoder, a type of ML model for data generation |
| Feature Store | Centralized repository for ML features |
| Route Graph | Graph structure representing train routes and connections |
| Validation Button | UI element that triggers real-time API validation |

---

## 15. References

- AI System Development Meeting: `.agent/workflows/ai_system_development.md`
- Route Engine Evolution: `.kiro/specs/route-engine-evolution/`
- CAT Model Requirements: `.kiro/specs/contextual-availability-transformer/requirements.md`
- Data Quality Framework: Internal documentation

---

**Document Version:** 1.0  
**Created:** 2026-05-08  
**Next Review:** 2026-05-15  
**Owner:** NOVA (ML Engineer)