import { useCallback, useEffect, useState } from 'react'
import { APIProvider, Map, useMap } from '@vis.gl/react-google-maps'

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || import.meta.env.GOOGLE_JS_API_KEY

function Polyline({ path, strokeColor = '#0A192F', strokeOpacity = 0.8, strokeWeight = 3 }) {
  const map = useMap()
  const [polyline, setPolyline] = useState(null)

  useEffect(() => {
    if (!map || !window.google?.maps) return

    const poly = new window.google.maps.Polyline({
      path,
      strokeColor,
      strokeOpacity,
      strokeWeight,
    })
    poly.setMap(map)
    setPolyline(poly)

    return () => {
      poly.setMap(null)
    }
  }, [map, path, strokeColor, strokeOpacity, strokeWeight])

  useEffect(() => {
    if (polyline && path) polyline.setPath(path)
  }, [polyline, path])

  return null
}

function LegacyMarker({ position, title, labelText, onClick }) {
  const map = useMap()

  useEffect(() => {
    if (!map || !window.google?.maps) return

    const marker = new window.google.maps.Marker({
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
    })

    let listener = null
    if (onClick) listener = marker.addListener('click', onClick)

    return () => {
      if (listener) listener.remove()
      marker.setMap(null)
    }
  }, [map, onClick, position, title, labelText])

  return null
}

function BoundsController({ stops }) {
  const map = useMap()

  useEffect(() => {
    if (!map || !stops?.length || !window.google?.maps) return

    const bounds = new window.google.maps.LatLngBounds()
    stops.forEach((stop) => bounds.extend({ lat: stop.lat, lng: stop.lng }))
    map.fitBounds(bounds, 60)
  }, [map, stops])

  return null
}

export default function MapRoute({ route, stops = [], onPinClick }) {
  const validRouteStops = (route?.stops ?? []).filter(
    (stop) => typeof stop.lat === 'number' && typeof stop.lng === 'number'
  )
  const path = validRouteStops.map((stop) => ({ lat: stop.lat, lng: stop.lng }))

  const handleClick = useCallback(
    (stopId) => {
      if (onPinClick) onPinClick(stopId)
    },
    [onPinClick]
  )

  if (!API_KEY) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-container">
        <p className="text-on-surface-muted text-sm">
          Map unavailable — set `GOOGLE_JS_API_KEY` or `VITE_GOOGLE_MAPS_API_KEY`.
        </p>
      </div>
    )
  }

  const defaultCenter =
    validRouteStops.length > 0
      ? { lat: validRouteStops[0].lat, lng: validRouteStops[0].lng }
      : { lat: 35.6762, lng: 139.6503 }

  return (
    <APIProvider apiKey={API_KEY}>
      <div style={{ width: '100%', height: '100%' }}>
        <Map
          defaultCenter={defaultCenter}
          defaultZoom={validRouteStops.length > 0 ? 13 : 12}
          disableDefaultUI={true}
          zoomControl={true}
          gestureHandling="greedy"
          style={{ width: '100%', height: '100%' }}
        >
          {validRouteStops.length > 0 && <BoundsController stops={validRouteStops} />}

          {path.length > 1 && <Polyline path={path} />}

          {validRouteStops.map((stop, index) => {
            const stopName = stops.find((candidate) => candidate.id === stop.place_id)?.name || `Stop ${index + 1}`
            return (
              <LegacyMarker
                key={stop.place_id}
                position={{ lat: stop.lat, lng: stop.lng }}
                onClick={() => handleClick(stop.place_id)}
                title={stopName}
                labelText={String(index + 1)}
              />
            )
          })}
        </Map>
      </div>
    </APIProvider>
  )
}
