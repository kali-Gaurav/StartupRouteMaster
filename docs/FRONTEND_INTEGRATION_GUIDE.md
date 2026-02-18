# 🚂 Frontend Integration Guide - Offline IRCTC System

## 📍 Quick Navigation

- **Backend Base URL**: `http://localhost:8000`
- **API Version**: `v2` (at `/api/v2/`)
- **No authentication required** for offline testing
- All responses include explicit status codes and error messages

## 🔌 Main API Endpoints

### 1️⃣ Search for Trains
**Endpoint:** `POST /api/v2/search/unified`

**When to call:** User enters source, destination, travel date, and clicks "Search"

**Request Body:**
```json
{
  "source": "Mumbai Central",
  "destination": "New Delhi",
  "travel_date": "2026-03-20",
  "num_passengers": 2,
  "coach_preference": "AC_THREE_TIER",
  "return_date": null,
  "is_tatkal": false
}
```

**Response (200 OK):**
```json
[
  {
    "journey_id": "JRN_654321",
    "num_segments": 2,
    "distance_km": 1414.2,
    "travel_time": "22:30",
    "num_transfers": 1,
    "is_direct": false,
    "cheapest_fare": 1259.92,
    "premium_fare": 2889.8,
    "has_overnight": true,
    "availability_status": "available"
  },
  {
    "journey_id": "JRN_789456",
    "num_segments": 1,
    "distance_km": 1400.0,
    "travel_time": "22:00",
    "num_transfers": 0,
    "is_direct": true,
    "cheapest_fare": 1200.0,
    "premium_fare": 3500.0,
    "has_overnight": true,
    "availability_status": "available"
  }
]
```

**Error Response (404):**
```json
{
  "message": "Stations not found",
  "suggestions_from": [
    {
      "name": "Mumbai Central",
      "code": "MMCT"
    }
  ],
  "suggestions_to": [
    {
      "name": "New Delhi",
      "code": "NDLS"
    }
  ]
}
```

### 2️⃣ Get Complete Journey Details
**Endpoint:** `GET /api/v2/journey/{journey_id}/unlock-details`

**When to call:** User clicks on a journey card to see full details before booking

**Query Parameters:**
```
journey_id=JRN_654321
travel_date=2026-03-20
coach_preference=AC_THREE_TIER
passenger_age=30
concession_type=null
```

**Response (200 OK):**
```json
{
  "journey": {
    "journey_id": "JRN_654321",
    "num_segments": 2,
    "distance_km": 1414.2,
    "travel_time": "22:30",
    "num_transfers": 1,
    "is_direct": false,
    "cheapest_fare": 1259.92,
    "premium_fare": 2889.8,
    "has_overnight": true,
    "availability_status": "available"
  },
  "segments": [
    {
      "segment_id": "SEG_0001",
      "train_number": "RJ",
      "train_name": "Rajdhani Express",
      "departure": {
        "station": "Mumbai Central",
        "code": "MMCT",
        "time": "06:00",
        "platform": "TBD"
      },
      "arrival": {
        "station": "Pune Junction",
        "code": "PUNE",
        "time": "10:00",
        "platform": "TBD"
      },
      "distance_km": 200.0,
      "travel_time": "04:00",
      "travel_time_minutes": 240,
      "running_days": "Daily",
      "halt_times": {},
      "availability": {
        "ac_first": 18,
        "ac_second": 48,
        "ac_third": 64,
        "sleeper": 72
      },
      "fare": {
        "base_fare": 1200.0,
        "currency": "INR",
        "tatkal_applicable": false
      }
    }
  ],
  "seat_allocation": {
    "allocated": [
      {
        "passenger": "John Doe",
        "seat": {
          "seat_id": "A_12_LOWER",
          "coach": "A",
          "seat_number": 12,
          "seat_type": "LOWER",
          "status": "booked"
        },
        "coach": "A",
        "fare_applicable": 2400.0
      }
    ],
    "waiting_list": [],
    "seat_details": "• John Doe: Coach A, Seat 12 (LOWER) - ₹2400.0"
  },
  "verification": {
    "overall_status": "verified",
    "is_bookable": true,
    "seat_check": {
      "status": "verified",
      "available": 34,
      "total": 64,
      "message": "Few seats available"
    },
    "schedule_check": {
      "status": "verified",
      "delay_minutes": 0,
      "message": "Train on schedule"
    },
    "restrictions": [],
    "warnings": []
  },
  "fare_breakdown": {
    "base_fare": 2280.0,
    "gst": 114.0,
    "total_fare": 2394.0,
    "cancellation_charges": 597.0,
    "applicable_discounts": []
  },
  "can_unlock_details": true
}
```

### 3️⃣ Station Autocomplete
**Endpoint:** `POST /api/v2/station-autocomplete`

**When to call:** User starts typing in source/destination field

**Query Parameters:**
```
query=Mumbai
```

**Response:**
```json
[
  {
    "stop_id": 1,
    "name": "Mumbai Central",
    "code": "MMCT",
    "city": "Mumbai",
    "state": "Maharashtra"
  },
  {
    "stop_id": 2,
    "name": "Mumbai Suburban",
    "code": "MUMB",
    "city": "Mumbai",
    "state": "Maharashtra"
  },
  {
    "stop_id": 3,
    "name": "Mumbai Dadar",
    "code": "DDR",
    "city": "Mumbai",
    "state": "Maharashtra"
  }
]
```

## 🎨 Frontend Components Structure

### Search Form Component
```javascript
const SearchForm = () => {
  // User input
  const [source, setSource] = useState('');
  const [destination, setDestination] = useState('');
  const [travelDate, setTravelDate] = useState('');
  const [numPassengers, setNumPassengers] = useState(1);
  const [coachPreference, setCoachPreference] = useState('AC_THREE_TIER');
  
  // On form submit
  const handleSearch = async () => {
    const resp = await fetch('http://localhost:8000/api/v2/search/unified', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source,
        destination,
        travel_date: travelDate,
        num_passengers: numPassengers,
        coach_preference: coachPreference
      })
    });
    
    const journeys = await resp.json();
    // Show results
  };
};
```

### Journey Card Component
```javascript
const JourneyCard = ({ journey, onSelect }) => {
  const handleUnlock = async () => {
    const resp = await fetch(
      `http://localhost:8000/api/v2/journey/${journey.journey_id}/unlock-details?` +
      `travel_date=${selectedDate}&` +
      `coach_preference=${coachPreference}&` +
      `passenger_age=30`,
      { method: 'GET' }
    );
    
    const details = await resp.json();
    onSelect(details);  // Show detailed view
  };
  
  return (
    <div onClick={handleUnlock}>
      <h3>{journey.is_direct ? 'Direct' : journey.num_transfers + ' Stops'}</h3>
      <p>₹{journey.cheapest_fare} - ₹{journey.premium_fare}</p>
      <p>{journey.travel_time}</p>
      <button>View Details</button>
    </div>
  );
};
```

### Journey Details Component
```javascript
const JourneyDetails = ({ journey, details }) => {
  return (
    <div>
      <h2>Journey Details</h2>
      
      {/* Segments */}
      {details.segments.map(seg => (
        <div key={seg.segment_id}>
          <h3>{seg.train_name} ({seg.train_number})</h3>
          <p>{seg.departure.station} {seg.departure.time}</p>
          <p>→ {seg.arrival.station} {seg.arrival.time}</p>
          <p>{seg.distance_km} km in {seg.travel_time}</p>
        </div>
      ))}
      
      {/* Verification Status */}
      <div className={`verification ${details.verification.overall_status}`}>
        <h3>Booking Status: {details.verification.overall_status}</h3>
        {details.verification.warnings.map(w => (
          <p key={w} className="warning">⚠ {w}</p>
        ))}
        {details.verification.restrictions.map(r => (
          <p key={r} className="restriction">🚫 {r}</p>
        ))}
      </div>
      
      {/* Seats */}
      <div>
        <h4>Seat Allocation</h4>
        {details.seat_allocation.allocated.map(seat => (
          <div key={seat.seat.seat_id}>
            {seat.passenger}: Coach {seat.coach}, Seat {seat.seat.seat_number} - ₹{seat.fare_applicable}
          </div>
        ))}
        {details.seat_allocation.waiting_list.length > 0 && (
          <div className="waiting">
            <p>{details.seat_allocation.waiting_list.length} on waiting list</p>
          </div>
        )}
      </div>
      
      {/* Fare */}
      <div>
        <h4>Fare Breakdown</h4>
        <p>Base: ₹{details.fare_breakdown.base_fare}</p>
        <p>GST: ₹{details.fare_breakdown.gst}</p>
        <p><strong>Total: ₹{details.fare_breakdown.total_fare}</strong></p>
        <p>Cancellation: ₹{details.fare_breakdown.cancellation_charges}</p>
      </div>
      
      {/* Book Button */}
      <button 
        disabled={!details.can_unlock_details}
        onClick={handleBooking}
      >
        {details.can_unlock_details ? 'Proceed to Booking' : 'Cannot Book'}
      </button>
    </div>
  );
};
```

## 📱 User Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. User enters source, destination, date                   │
│     Coach preference: AC_THREE_TIER, Passengers: 2          │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
        POST /api/v2/search/unified
                    │
         ┌──────────┴──────────┐
         │ Loading...          │
         └──────────┬──────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Show search results (journey cards)                      │
│     • Direct trains at top                                   │
│     • Sorted by price                                        │
│     • Show: fare range, time, transfers                      │
│     • "View Details" button                                  │
└───────────────────┬─────────────────────────────────────────┘
                    │
         User clicks "View Details"
                    │
                    ▼
   GET /api/v2/journey/{id}/unlock-details
                    │
         ┌──────────┴──────────┐
         │ Loading details...  │
         └──────────┬──────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Show complete journey details                            │
│     ✓ Train name, number                                     │
│     ✓ Departure/arrival stations and times                  │
│     ✓ Distance and travel time                              │
│     ✓ Run days and platforms                                │
│     ✓ Seat allocation (Coach A, Seat 12, Lower berth)      │
│     ✓ Fare breakdown (base, GST, total, cancellation)      │
│     ✓ Verification status                                   │
│     ✓ Warnings (few seats left, train delayed, etc.)       │
│     • "Proceed to Booking" button                           │
└───────────────────┬─────────────────────────────────────────┘
                    │
         User clicks "Proceed to Booking"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Booking confirmation                                     │
│     • Passenger details form                                │
│     • Seat confirmation                                      │
│     • Final fare                                             │
│     • Payment integration (future)                           │
└─────────────────────────────────────────────────────────────┘
```

## ⚠️ Error Handling

### Station Not Found (404)
```javascript
if (response.status === 404) {
  const error = await response.json();
  // Show suggestions
  console.log(error.suggestions_from);  // Alternative stations
  console.log(error.suggestions_to);
}
```

### Invalid Input (400)
```javascript
if (response.status === 400) {
  const error = await response.json();
  // Show validation errors
  console.log(error.errors);
}
```

### Server Error (500)
```javascript
if (response.status === 500) {
  // Show "try again later"
}
```

### Service Unavailable (503)
```javascript
if (response.status === 503) {
  // Show "trains not available"
}
```

## 🎛️ Coach Types and Names

For dropdown/selection:
```javascript
const COACH_TYPES = {
  'AC_FIRST_CLASS': '1A - AC First Class (₹3500 avg)',
  'AC_TWO_TIER': '2A - AC 2-Tier (₹2500 avg)',
  'AC_THREE_TIER': '3A - AC 3-Tier (₹1500 avg)',
  'FIRST_CLASS': 'FC - First Class (₹1200 avg)',
  'SLEEPER': 'SL - Sleeper (₹600 avg)',
  'SECOND_CLASS': '2S - Second Class (₹200 avg)',
  'GENERAL': 'GN - General/Unreserved (₹100 avg)'
};
```

## 🎫 Concession Types

For concession selection dropdown:
```javascript
const CONCESSION_TYPES = [
  { value: null, label: 'None' },
  { value: 'student', label: 'Student (25% off)' },
  { value: 'senior_citizen', label: 'Senior Citizen (25% off)' },
  { value: 'military', label: 'Military (20% off)' },
  { value: 'disabled', label: 'Person with Disability (50% off)' }
];
```

## 📊 Status Display

```javascript
const STATUS_DISPLAY = {
  'verified': { icon: '✅', color: 'green', text: 'All Verified' },
  'delayed': { icon: '⚠️', color: 'orange', text: 'Train Delayed' },
  'cancelled': { icon: '❌', color: 'red', text: 'Cancelled' },
  'pending': { icon: '⏳', color: 'blue', text: 'Waiting List Only' }
};
```

## 🧪 Testing Without Backend

Use mock data to build UI before backend is ready:

```javascript
const MOCK_SEARCH_RESPONSE = [
  {
    journey_id: "JRN_123456",
    num_segments: 1,
    distance_km: 1400,
    travel_time: "22:30",
    num_transfers: 0,
    is_direct: true,
    cheapest_fare: 1200,
    premium_fare: 3500,
    has_overnight: true,
    availability_status: "available"
  }
];

// In component:
const journeys = useMemo(() => 
  process.env.USE_MOCK === 'true' ? MOCK_SEARCH_RESPONSE : null,
  []
);
```

## 🚀 Ready to Integrate!

Your backend is **fully functional** with:
- ✅ Complete journey reconstruction
- ✅ Seat allocation
- ✅ Fare calculation
- ✅ Verification checks
- ✅ Error handling
- ✅ Offline testing endpoints

**Next Steps:**
1. Integrate search endpoint first
2. Integrate journey details endpoint
3. Add payment flow
4. Go LIVE! 🎉

Questions? Check `IRCTC_OFFLINE_SYSTEM_GUIDE.md` for technical details.
