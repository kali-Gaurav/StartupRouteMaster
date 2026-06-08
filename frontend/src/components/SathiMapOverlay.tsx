import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Shield, MapPin, Star, Phone, CheckCircle2, Navigation } from 'lucide-react';
import { cn } from '@/lib/utils';
import { LocationService } from '@/lib/locationService';

// Custom Sathi Marker Icon
const sathiIcon = L.divIcon({
  className: 'custom-sathi-icon',
  html: `
    <div class="relative flex items-center justify-center w-10 h-10 bg-emerald-500 rounded-full border-2 border-white shadow-lg animate-in zoom-in duration-300">
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      <div class="absolute -top-1 -right-1 w-3 h-3 bg-blue-400 rounded-full border border-white animate-pulse"></div>
    </div>
  `,
  iconSize: [40, 40],
  iconAnchor: [20, 40],
  popupAnchor: [0, -40]
});

// User Location Marker
const userIcon = L.divIcon({
  className: 'user-marker-icon',
  html: `
    <div class="relative flex items-center justify-center w-8 h-8 bg-blue-500 rounded-full border-2 border-white shadow-xl">
      <div class="w-3 h-3 bg-white rounded-full animate-ping absolute"></div>
      <div class="w-3 h-3 bg-white rounded-full"></div>
    </div>
  `,
  iconSize: [32, 32],
  iconAnchor: [16, 16]
});

interface SathiLocation {
  id: string;
  name: string;
  lat: number;
  lng: number;
  rating: number;
  specializations: string[];
  phone?: string;
}

interface SathiMapOverlayProps {
  className?: string;
  onSathiSelect?: (sathi: SathiLocation) => void;
}

// Component to handle map centering
function MapCenterer({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom());
  }, [center, map]);
  return null;
}

export function SathiMapOverlay({ className, onSathiSelect }: SathiMapOverlayProps) {
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
  const [nearbySathis, setNearbySathis] = useState<SathiLocation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 1. Fetch User Location
  useEffect(() => {
    LocationService.requestLocation()
      .then(loc => {
        if (loc) {
          setUserLocation([loc.latitude, loc.longitude]);
          fetchNearbySathis(loc.latitude, loc.longitude);
        }
      })
      .catch(err => {
        console.error("Location access denied", err);
        setError("Location access required for 'Sathi Near Me'");
        setIsLoading(false);
      });
  }, []);

  // 2. Fetch Nearby Sathis from V2 API
  const fetchNearbySathis = async (lat: number, lng: number) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/v2/sathi/nearby?lat=${lat}&lng=${lng}&radius=50`);
      if (response.ok) {
        const result = await response.json();
        setNearbySathis(result.data || []);
      }
    } catch (err) {
      console.error("Failed to fetch nearby Sathis", err);
    } finally {
      setIsLoading(false);
    }
  };

  if (error) {
    return (
      <div className={cn("bg-muted/30 rounded-2xl flex flex-col items-center justify-center p-8 text-center", className)}>
        <MapPin className="w-12 h-12 text-muted-foreground mb-4 opacity-20" />
        <p className="text-sm font-medium text-muted-foreground">{error}</p>
        <button 
          onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-xs font-bold"
        >
          Enable Location
        </button>
      </div>
    );
  }

  const defaultCenter: [number, number] = [28.6139, 77.2090]; // Delhi

  return (
    <div className={cn("relative group", className)}>
      <MapContainer 
        center={userLocation || defaultCenter} 
        zoom={13} 
        className="w-full h-full rounded-2xl z-0 overflow-hidden border border-border/50 shadow-inner"
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          className="sathi-map-tiles"
        />
        
        {userLocation && (
          <>
            <MapCenterer center={userLocation} />
            <Marker position={userLocation} icon={userIcon}>
              <Popup className="sathi-popup">
                <div className="p-1 font-bold text-xs">You are here</div>
              </Popup>
            </Marker>
            <Circle 
              center={userLocation}
              radius={5000}
              pathOptions={{ 
                color: '#10b981', 
                fillColor: '#10b981', 
                fillOpacity: 0.05,
                weight: 1,
                dashArray: '5, 5'
              }}
            />
          </>
        )}

        {nearbySathis.map((sathi) => (
          <Marker 
            key={sathi.id} 
            position={[sathi.lat, sathi.lng]} 
            icon={sathiIcon}
            eventHandlers={{
              click: () => onSathiSelect?.(sathi)
            }}
          >
            <Popup className="sathi-popup">
              <div className="w-48 p-1">
                <div className="flex items-center gap-2 mb-2">
                  <div className="p-1.5 bg-emerald-100 rounded-lg">
                    <Shield className="w-3.5 h-3.5 text-emerald-600" />
                  </div>
                  <div>
                    <div className="text-xs font-black uppercase tracking-tight">{sathi.name}</div>
                    <div className="flex items-center gap-1">
                       {[...Array(5)].map((_, i) => (
                         <Star key={i} className={cn("w-2 h-2", i < sathi.rating ? "fill-amber-400 text-amber-400" : "text-muted")} />
                       ))}
                       <span className="text-[10px] font-bold text-muted-foreground ml-1">{sathi.rating}</span>
                    </div>
                  </div>
                </div>
                
                <div className="space-y-1.5">
                  <div className="flex flex-wrap gap-1">
                    {sathi.specializations.slice(0, 2).map((spec, i) => (
                      <span key={i} className="px-1.5 py-0.5 bg-secondary text-[8px] font-black rounded uppercase border border-border/50">
                        {spec.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                  
                  <div className="flex items-center gap-2 pt-2 border-t border-border mt-2">
                     <button className="flex-1 py-1.5 bg-primary text-white text-[10px] font-black rounded-md flex items-center justify-center gap-1.5 uppercase tracking-tighter hover:bg-primary/90 transition-colors">
                       <Navigation className="w-3 h-3" /> Request Guide
                     </button>
                  </div>
                </div>
                
                <div className="mt-2 flex items-center gap-1 text-[9px] font-bold text-emerald-600">
                  <CheckCircle2 className="w-2.5 h-2.5" /> Identity Verified
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Floating UI Elements */}
      <div className="absolute top-4 left-4 z-10 space-y-2">
        <div className="bg-background/90 backdrop-blur-md px-3 py-1.5 rounded-full border border-border/50 shadow-lg flex items-center gap-2 animate-in slide-in-from-left duration-500">
           <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
           <span className="text-[10px] font-black uppercase tracking-widest text-foreground">
             {nearbySathis.length} Active Sathis Nearby
           </span>
        </div>
      </div>

      {isLoading && (
        <div className="absolute inset-0 z-20 bg-background/50 backdrop-blur-[2px] flex items-center justify-center rounded-2xl">
           <div className="flex flex-col items-center gap-3">
             <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
             <span className="text-[10px] font-black uppercase tracking-widest text-primary">Scanning Perimeter...</span>
           </div>
        </div>
      )}

      <button 
        onClick={() => userLocation && fetchNearbySathis(userLocation[0], userLocation[1])}
        className="absolute bottom-4 right-4 z-10 p-2.5 bg-background/90 backdrop-blur-md rounded-xl border border-border/50 shadow-lg hover:bg-background transition-colors"
        title="Refresh Perimeter"
      >
        <Navigation className="w-4 h-4 text-primary" />
      </button>
    </div>
  );
}
