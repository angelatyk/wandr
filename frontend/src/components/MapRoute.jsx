import { useCallback } from 'react';
import {
  APIProvider,
  Map,
  AdvancedMarker,
  Polyline,
  useMap,
} from '@vis.gl/react-google-maps';

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

/**
 * Inner component that auto-fits map bounds when stops change.
 * Must be rendered inside <Map> so it can call useMap().
 */
function BoundsController({ stops }) {
  const map = useMap();

  if (map && stops.length > 0) {
    // Fit all stop positions into view
    const bounds = new window.google.maps.LatLngBounds();
    stops.forEach(s => bounds.extend({ lat: s.lat, lng: s.lng }));
    map.fitBounds(bounds, 60);
  }

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
    <APIProvider apiKey={API_KEY} libraries={['marker']}>
      <Map
        defaultCenter={defaultCenter}
        defaultZoom={validStops.length > 0 ? 13 : 12}
        mapId={import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID'}
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
          <AdvancedMarker
            key={stop.place_id}
            position={{ lat: stop.lat, lng: stop.lng }}
            onClick={() => handleClick(stop.place_id)}
            title={`Stop ${index + 1}`}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: '#0A192F',
                border: '2.5px solid #D4AF37',
                color: 'white',
                fontWeight: 700,
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                boxShadow: '0 2px 8px rgba(0,0,0,0.35)',
                fontFamily: 'Inter, sans-serif',
                userSelect: 'none',
                transition: 'transform 0.15s',
              }}
            >
              {index + 1}
            </div>
          </AdvancedMarker>
        ))}
      </Map>
    </APIProvider>
  );
}
