# Implementation Plan: Unlock Payment Verification Integration

**Date:** 2026-02-23  
**Goal:** Integrate RapidAPI seat availability and fare verification into unlock payment flow

---

## 🔍 Current State Analysis

### Unlock Payment Flow (Current)
1. User clicks "Unlock" button
2. Payment order created (`POST /api/payments/create_order`)
3. User pays via Razorpay
4. Payment verified (`POST /api/payments/verify`)
5. Route unlocked (no verification)

### Issue Identified
- ❌ **No seat availability verification during unlock**
- ❌ **No fare verification during unlock**
- ❌ **Verification happens only in `DataProvider` but not called during unlock**

---

## ✅ Required Changes

### 1. Add Verification to Unlock Payment Flow

**Location:** `backend/api/payments.py` - `create_payment_order()` endpoint

**Change:**
- Before creating payment order, verify seat availability and fare
- Use `DataProvider.verify_seat_availability_unified()` and `verify_fare_unified()`
- Only proceed if verification successful
- Cache results to avoid duplicate API calls

### 2. Extract Route Information

**Required Data:**
- Train number
- From station code
- To station code
- Travel date
- Class type (SL, 3AC)

**Source:** Route model from database

### 3. Add Verification Response to Frontend

**Change:**
- Return verification results in unlock payment response
- Display seat availability and fare to user
- Show verification status

---

## 📝 Implementation Steps

### Step 1: Update Unlock Payment Endpoint

**File:** `backend/api/payments.py`

**Function:** `create_payment_order()` - Unlock payment section

**Changes:**
1. Extract route information (train number, stations, date)
2. Call `DataProvider` verification methods
3. Verify seat availability (SL, 3AC)
4. Verify fare
5. Return verification results
6. Only create payment if verification successful

### Step 2: Create Verification Helper Function

**File:** `backend/api/payments.py` (or new `backend/services/verification_service.py`)

**Function:** `verify_route_for_unlock()`

**Purpose:**
- Centralized verification logic
- Handles RapidAPI calls
- Manages caching
- Returns structured results

### Step 3: Update Frontend to Display Verification

**File:** `src/components/PaymentModal.tsx` or unlock component

**Changes:**
- Display seat availability after verification
- Display fare information
- Show verification status

### Step 4: Add Error Handling

**Changes:**
- Handle RapidAPI failures gracefully
- Fallback to database if API unavailable
- Log errors appropriately
- Return user-friendly error messages

---

## 🔧 Code Changes Required

### Change 1: Update `create_payment_order()` - Unlock Section

```python
# In backend/api/payments.py

# Add import
from backend.core.route_engine.data_provider import DataProvider

# In create_payment_order() - unlock payment section:
else:
    # Handle Unlock Payment
    try:
        if unlock_service.is_route_unlocked(current_user.id, request.route_id):
             return {"success": True, "message": "Route already unlocked.", "unlocked": True}

        # NEW: Verify seat availability and fare before creating payment
        data_provider = DataProvider()
        data_provider.detect_available_features()
        
        # Extract route information
        route = db.query(RouteModel).filter(RouteModel.id == request.route_id).first()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        
        # Extract train number and stations from route
        # Assuming route has train_number, source_station_code, destination_station_code
        train_number = getattr(route, 'train_number', None)
        from_station = getattr(route, 'source_station_code', None)
        to_station = getattr(route, 'destination_station_code', None)
        travel_date = request.travel_date
        
        verification_results = {}
        
        # Verify seat availability for SL and 3AC
        if train_number and from_station and to_station:
            # Verify SL
            sl_verification = await data_provider.verify_seat_availability_unified(
                trip_id=route.id,  # Use route ID as trip_id
                travel_date=datetime.combine(travel_date, datetime.min.time()),
                coach_preference="SLEEPER",
                train_number=train_number,
                from_station=from_station,
                to_station=to_station,
                quota="GN"
            )
            
            # Verify 3AC
            ac3_verification = await data_provider.verify_seat_availability_unified(
                trip_id=route.id,
                travel_date=datetime.combine(travel_date, datetime.min.time()),
                coach_preference="AC_THREE_TIER",
                train_number=train_number,
                from_station=from_station,
                to_station=to_station,
                quota="GN"
            )
            
            # Verify fare for SL
            sl_fare = await data_provider.verify_fare_unified(
                segment_id=route.id,
                coach_preference="SLEEPER",
                train_number=train_number,
                from_station=from_station,
                to_station=to_station
            )
            
            # Verify fare for 3AC
            ac3_fare = await data_provider.verify_fare_unified(
                segment_id=route.id,
                coach_preference="AC_THREE_TIER",
                train_number=train_number,
                from_station=from_station,
                to_station=to_station
            )
            
            verification_results = {
                "sl_availability": sl_verification,
                "ac3_availability": ac3_verification,
                "sl_fare": sl_fare,
                "ac3_fare": ac3_fare
            }
        
        # Create payment order
        order_response = await payment_service.create_order(
            amount_rupees=UNLOCK_PRICE,
            receipt_id=f"unlock_{request.route_id}_{current_user.id}",
            customer_email=current_user.email,
            description=f"Unlock Route {route.source} to {route.destination}",
            idempotency_key=f"unlock_{request.route_id}_{current_user.id}",
        )

        if not order_response.get("success"):
            raise HTTPException(status_code=400, detail=order_response.get("error"))

        razorpay_order_id = order_response["order_id"]
        new_payment = PaymentModel(
            razorpay_order_id=razorpay_order_id,
            status="pending",
            amount=UNLOCK_PRICE,
        )
        db.add(new_payment)
        db.commit()
        db.refresh(new_payment)
        
        # Link payment to unlock intent
        unlocked_route = UnlockedRoute(
            user_id=current_user.id,
            route_id=request.route_id,
            payment_id=new_payment.id,
            is_active=False # Becomes active after payment verification
        )
        db.add(unlocked_route)
        db.commit()

        return {
            "success": True,
            "order": order_response,
            "payment_id": new_payment.id,
            "verification": verification_results  # NEW: Include verification results
        }
```

### Change 2: Extract Route Information Properly

**Issue:** Route model may not have direct `train_number`, `source_station_code` fields

**Solution:** Query related tables to get this information

```python
# Get route segments to extract train and station info
from backend.database.models import RouteSegment, Trip, StopTime, Stop

# Query route segments
segments = db.query(RouteSegment).filter(
    RouteSegment.route_id == route.id
).all()

if segments:
    first_segment = segments[0]
    # Get trip information
    trip = db.query(Trip).filter(Trip.id == first_segment.trip_id).first()
    if trip:
        train_number = trip.train_number
        
        # Get station codes
        from_stop_time = db.query(StopTime).filter(
            StopTime.trip_id == trip.id,
            StopTime.stop_sequence == 0
        ).first()
        to_stop_time = db.query(StopTime).filter(
            StopTime.trip_id == trip.id,
            StopTime.stop_sequence == len(segments) - 1
        ).first()
        
        if from_stop_time and to_stop_time:
            from_station = db.query(Stop).filter(Stop.id == from_stop_time.stop_id).first()
            to_station = db.query(Stop).filter(Stop.id == to_stop_time.stop_id).first()
            
            from_station_code = from_station.code if from_station else None
            to_station_code = to_station.code if to_station else None
```

---

## 🧪 Testing Strategy

### Test Case 1: Successful Verification
- Route with valid train number and stations
- RapidAPI returns success
- Verification results included in response

### Test Case 2: Cache Hit
- Second unlock for same route
- No RapidAPI call made
- Cached results returned

### Test Case 3: RapidAPI Failure
- RapidAPI returns error
- Fallback to database
- Unlock still proceeds

### Test Case 4: Missing Route Information
- Route without train number
- Graceful handling
- Error message returned

---

## 📊 API Usage Impact

### Before (Current)
- 0 RapidAPI calls during unlock

### After (With Verification)
- 4 RapidAPI calls per unlock (SL seat + SL fare + 3AC seat + 3AC fare)
- With caching: Only first unlock makes calls, subsequent unlocks use cache

### Optimization
- Cache TTL: 15 minutes (current)
- Cache key: `train_no:from_stn:to_stn:date:quota:class_type`
- Expected cache hit rate: >50% (if users unlock same routes)

---

## ✅ Success Criteria

1. ✅ Seat availability verified during unlock (SL, 3AC)
2. ✅ Fare verified during unlock (SL, 3AC)
3. ✅ Verification results returned to frontend
4. ✅ Caching working correctly
5. ✅ Fallback working if RapidAPI fails
6. ✅ API usage within budget (7000/month)

---

## 🚀 Next Steps

1. **Review Implementation Plan**
2. **Implement Code Changes**
3. **Test Verification Integration**
4. **Update Frontend to Display Results**
5. **Monitor API Usage**
6. **Optimize Based on Results**
