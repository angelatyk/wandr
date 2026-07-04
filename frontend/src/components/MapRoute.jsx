import { useCallback, useEffect, useState } from 'react';
import {
  APIProvider,
  Map,
  useMap,
} from '@vis.gl/react-google-maps';

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

/**
 * Custom Polyline component for @vis.gl/react-google-maps.
 * Draws a path connecting coordinates on the map.
 */
function Polyline({ path, strokeColor, strokeOpacity, strokeWeight }) {
  const map = useMap();
  const [polyline, setPolyline] = useState(null);

  useEffect(() => {
    if (!map || !window.google?.maps) return;

    const poly = new window.google.maps.Polyline({
      path: path,
      strokeColor: strokeColor || '#0A192F',
      strokeOpacity: strokeOpacity || 0.8,
      strokeWeight: strokeWeight || 3,
    });

    poly.setMap(map);
    setPolyline(poly);

    return () => {
      poly.setMap(null);
    };
  }, [map]);

  useEffect(() => {
    if (polyline && path) {
      polyline.setPath(path);
    }
  }, [polyline, path]);

  return null;
}

/**
 * Custom legacy Marker component for @vis.gl/react-google-maps.
 * Does not require any Map ID to render, preventing MapId-related load errors.
 */
function LegacyMarker({ position, title, labelText, onClick }) {
  const map = useMap();
  const [marker, setMarker] = useState(null);

  useEffect(() => {
    if (!map || !window.google?.maps) return;

    const m = new window.google.maps.Marker({
      position,
      map,
      title,
      label: {
        text: labelText,
        color: '#FFFFFF',
        fontWeight: 'bold',
        fontSize: '13px',
      },
      icon: {
        path: window.google.maps.SymbolPath.CIRCLE,
        scale: 15,
        fillColor: '#0A192F',
        fillOpacity: 1,
        strokeColor: '#D4AF37',
        strokeWeight: 2.5,
      },
    });

    if (onClick) {
      const listener = m.addListener('click', onClick);
      return () => {
        listener.remove();
        m.setMap(null);
      };
    }

    setMarker(m);

    return () => {
      m.setMap(null);
    };
  }, [map, onClick]);

  useEffect(() => {
    if (marker && position) {
      marker.setPosition(position);
    }
  }, [marker, position]);

  return null;
}

/**
 * Inner component that auto-fits map bounds when stops change.
 * Must be rendered inside <Map> so it can call useMap().
 */
function BoundsController({ stops }) {
  const map = useMap();

  useEffect(() => {
    if (!map || !stops || stops.length === 0 || !window.google?.maps) return;

    const bounds = new window.google.maps.LatLngBounds();
    stops.forEach(s => bounds.extend({ lat: s.lat, lng: s.lng }));
    map.fitBounds(bounds, 60);
  }, [map, stops]);

  return null;
}

/**
 * MapRoute — Google Map with numbered stop markers and a connecting route line.
 *
 * Props:
 *   route       — RouteModel { stops: RouteStop[] }
 *   onPinClick  — (stopId: string) => void
 */
export default function MapRoute({ route, onPinClick }) {
  const validStops = (route?.stops ?? []).filter(
    s => typeof s.lat === 'number' && typeof s.lng === 'number'
  );

  const path = validStops.map(s => ({ lat: s.lat, lng: s.lng }));

  const handleClick = useCallback(
    stopId => {
      if (onPinClick) onPinClick(stopId);
    },
    [onPinClick]
  );

  if (!API_KEY) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-container">
        <p className="text-on-surface-muted text-sm">
          Map unavailable — set VITE_GOOGLE_MAPS_API_KEY in frontend/.env
        </p>
      </div>
    );
  }

  // Default center (Toronto) shown while route is loading
  const defaultCenter =
    validStops.length > 0
      ? { lat: validStops[0].lat, lng: validStops[0].lng }
      : { lat: 43.65107, lng: -79.347015 };

  return (
    <APIProvider apiKey={API_KEY}>
      <div style={{ width: '100%', height: '100%' }}>
        <Map
          defaultCenter={defaultCenter}
          defaultZoom={validStops.length > 0 ? 13 : 12}
          disableDefaultUI={true}
          zoomControl={true}
          gestureHandling="greedy"
          style={{ width: '100%', height: '100%' }}
        >
          {/* Auto-fit bounds when stops are available */}
          {validStops.length > 0 && <BoundsController stops={validStops} />}

          {/* Route polyline */}
          {path.length > 1 && (
            <Polyline
              path={path}
              strokeColor="#0A192F"
              strokeOpacity={0.8}
              strokeWeight={3}
            />
          )}

          {/* Numbered markers */}
          {validStops.map((stop, index) => (
            <LegacyMarker
              key={stop.place_id}
              position={{ lat: stop.lat, lng: stop.lng }}
              onClick={() => handleClick(stop.place_id)}
              title={stop.name || `Stop ${index + 1}`}
              labelText={String(index + 1)}
            />
          ))}
        </Map>
      </div>
    </APIProvider>
  );
}
