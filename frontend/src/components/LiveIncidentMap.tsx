import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { cn } from '@/lib/utils';

// Fix for default marker icons in Leaflet + React
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

interface LiveIncidentMapProps {
  incidents: any[];
  onIncidentSelect: (incident: any) => void;
  selectedId?: string;
  className?: string;
}

export function LiveIncidentMap({ incidents, onIncidentSelect, selectedId, className }: LiveIncidentMapProps) {
  // Center on India by default
  const center: [number, number] = [20.5937, 78.9629]; 

  return (
    <MapContainer 
      center={center} 
      zoom={5} 
      className={cn("w-full h-full rounded-2xl z-0", className)}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      
      {incidents.map((incident) => (
        <React.Fragment key={incident.id}>
          {/* Subtask 31.5: Breadcrumb Path Rendering */}
          {incident.location_history && incident.location_history.length > 1 && (
            <Polyline 
              positions={incident.location_history.map((h: any) => [h.lat, h.lng])}
              pathOptions={{ 
                color: incident.priority === 'critical' ? '#ef4444' : '#f97316', 
                weight: 3,
                dashArray: '5, 10',
                opacity: 0.6
              }}
            />
          )}

          {/* Pulsing Alert Area */}
          <Circle 
            center={[incident.lat, incident.lng]}
            pathOptions={{ 
                color: incident.id === selectedId ? 'red' : 'orange',
                fillColor: incident.id === selectedId ? 'red' : 'orange',
                fillOpacity: 0.2 
            }}
            radius={5000} // 5km deviation threshold
          />
          
          <Marker 
            position={[incident.lat, incident.lng]}
            eventHandlers={{
              click: () => onIncidentSelect(incident),
            }}
          >
            <Popup>
              <div className="text-xs">
                <div className="font-bold">{incident.name}</div>
                <div className="text-red-600 font-bold uppercase">{incident.status}</div>
                <div>Train: {incident.trainNo}</div>
              </div>
            </Popup>
          </Marker>
        </React.Fragment>
      ))}
    </MapContainer>
  );
}

import React from 'react';
