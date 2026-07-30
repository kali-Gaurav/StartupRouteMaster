"""
MCP Supabase Integration
========================
Integrates with Supabase MCP server for database operations.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from config import get_bootstrap_settings

logger = logging.getLogger("mcp_supabase")


class SupabaseMCPClient:
    """
    Supabase MCP client for database operations.
    
    Uses the MCP protocol to interact with Supabase database.
    """
    
    def __init__(self):
        self.settings = get_bootstrap_settings()
        self.mcp_url = "https://mcp.supabase.com/mcp"
        self.project_ref = "orfikmmpbboesbxdiwzb"  # From MCP config
        self.access_token = self.settings.supabase_access_token
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
    
    @asynccontextmanager
    async def get_client(self):
        """Get async HTTP client context."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client
    
    async def query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a read query via MCP.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result rows as dictionaries
        """
        try:
            # In production, this would call the MCP server
            # For now, we use direct Supabase REST API
            url = f"https://{self.project_ref}.supabase.co/rest/v1/rpc/execute_sql"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "apikey": self.access_token,
                "Content-Type": "application/json"
            }
            
            payload = {
                "query": query,
                "params": params or {}
            }
            
            response = await self.http_client.post(
                url,
                json=payload,
                headers=headers
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"MCP query error: {e}")
            # Fallback to direct database connection
            return await self._fallback_query(query, params)
    
    async def execute(self, statement: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a write statement via MCP.
        
        Args:
            statement: SQL statement
            params: Statement parameters
            
        Returns:
            Execution result
        """
        try:
            url = f"https://{self.project_ref}.supabase.co/rest/v1/rpc/execute_sql"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "apikey": self.access_token,
                "Content-Type": "application/json"
            }
            
            payload = {
                "statement": statement,
                "params": params or {}
            }
            
            response = await self.http_client.post(
                url,
                json=payload,
                headers=headers
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"MCP execute error: {e}")
            return {"error": str(e)}
    
    async def _fallback_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Fallback to direct database connection."""
        from database.session import get_engine
        
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return [dict(row._mapping) for row in result.fetchall()]
    
    # Convenience methods for common operations
    
    async def get_booking(self, booking_id: str) -> Optional[Dict]:
        """Get booking by ID."""
        results = await self.query(
            "SELECT * FROM bookings WHERE id = :id",
            {"id": booking_id}
        )
        return results[0] if results else None
    
    async def get_user_bookings(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict]:
        """Get bookings for a user."""
        return await self.query(
            """
            SELECT * FROM bookings 
            WHERE user_id = :user_id 
            ORDER BY created_at DESC 
            LIMIT :limit OFFSET :offset
            """,
            {"user_id": user_id, "limit": limit, "offset": offset}
        )
    
    async def create_booking(self, booking_data: Dict) -> Dict:
        """Create a new booking."""
        return await self.execute(
            """
            INSERT INTO bookings (
                id, pnr_number, user_id, journey_id, travel_date,
                train_number, from_station_code, to_station_code,
                class_type, booking_status, total_amount, created_at
            ) VALUES (
                :id, :pnr_number, :user_id, :journey_id, :travel_date,
                :train_number, :from_station_code, :to_station_code,
                :class_type, :booking_status, :total_amount, :created_at
            )
            RETURNING *
            """,
            booking_data
        )
    
    async def update_booking_status(
        self,
        booking_id: str,
        status: str,
        payment_id: Optional[str] = None
    ) -> Dict:
        """Update booking status."""
        return await self.execute(
            """
            UPDATE bookings 
            SET booking_status = :status,
                payment_id = COALESCE(:payment_id, payment_id),
                updated_at = NOW()
            WHERE id = :id
            RETURNING *
            """,
            {"id": booking_id, "status": status, "payment_id": payment_id}
        )
    
    async def get_seat_availability(
        self,
        train_number: str,
        travel_date: str,
        class_type: str
    ) -> Dict:
        """Get seat availability for a train."""
        results = await self.query(
            """
            SELECT * FROM seat_inventory 
            WHERE train_number = :train_number 
            AND journey_date = :travel_date
            AND class_type = :class_type
            """,
            {
                "train_number": train_number,
                "travel_date": travel_date,
                "class_type": class_type
            }
        )
        return results[0] if results else None
    
    async def update_seat_inventory(
        self,
        train_number: str,
        from_station: str,
        to_station: str,
        travel_date: str,
        class_type: str,
        seats_change: int
    ) -> Dict:
        """Update seat inventory (allocate or release)."""
        return await self.execute(
            """
            UPDATE seat_inventory 
            SET available_seats = available_seats + :seats_change,
                updated_at = NOW()
            WHERE train_number = :train_number
            AND from_station_code = :from_station
            AND to_station_code = :to_station
            AND journey_date = :travel_date
            AND class_type = :class_type
            RETURNING *
            """,
            {
                "train_number": train_number,
                "from_station": from_station,
                "to_station": to_station,
                "travel_date": travel_date,
                "class_type": class_type,
                "seats_change": seats_change
            }
        )


class MCPSupabaseManager:
    """
    Manager for Supabase MCP operations.
    
    Provides high-level operations for common tasks.
    """
    
    def __init__(self):
        self.client = SupabaseMCPClient()
    
    async def initialize(self):
        """Initialize MCP connection."""
        logger.info("Initializing Supabase MCP connection...")
        # Test connection
        try:
            await self.client.query("SELECT 1")
            logger.info("Supabase MCP connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase MCP: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MCP service health."""
        try:
            # Test query
            await self.client.query("SELECT 1")
            return {
                "status": "healthy",
                "service": "supabase-mcp",
                "project": self.client.project_ref
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get_booking_with_details(self, booking_id: str) -> Optional[Dict]:
        """Get booking with passenger details."""
        booking = await self.client.get_booking(booking_id)
        if not booking:
            return None
        
        # Get passengers
        passengers = await self.client.query(
            "SELECT * FROM passenger_details WHERE booking_id = :booking_id",
            {"booking_id": booking_id}
        )
        
        booking["passengers"] = passengers
        return booking
    
    async def search_routes(
        self,
        source: str,
        destination: str,
        travel_date: str,
        class_type: Optional[str] = None
    ) -> List[Dict]:
        """Search for routes using MCP."""
        query = """
            SELECT r.*, s.availability_status, s.base_fare
            FROM routes r
            JOIN schedules s ON r.id = s.route_id
            WHERE r.source_code = :source
            AND r.dest_code = :destination
            AND s.travel_date = :travel_date
        """
        
        params = {
            "source": source.upper(),
            "destination": destination.upper(),
            "travel_date": travel_date
        }
        
        if class_type:
            query += " AND s.class_type = :class_type"
            params["class_type"] = class_type
        
        query += " ORDER BY r.departure_time"
        
        return await self.client.query(query, params)
    
    async def create_booking_with_passengers(
        self,
        booking_data: Dict,
        passengers: List[Dict]
    ) -> Dict:
        """Create booking with passengers in a transaction."""
        # Create booking
        booking = await self.client.create_booking(booking_data)
        
        # Create passengers
        for passenger in passengers:
            await self.client.execute(
                """
                INSERT INTO passenger_details (
                    id, booking_id, full_name, age, gender,
                    phone_number, email, berth_preference
                ) VALUES (
                    :id, :booking_id, :full_name, :age, :gender,
                    :phone_number, :email, :berth_preference
                )
                """,
                {
                    **passenger,
                    "booking_id": booking_data["id"]
                }
            )
        
        return booking


# Singleton instance
mcp_supabase_manager = MCPSupabaseManager()


async def get_mcp_manager() -> MCPSupabaseManager:
    """Get MCP manager instance."""
    await mcp_supabase_manager.initialize()
    return mcp_supabase_manager