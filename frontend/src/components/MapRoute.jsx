import { useCallback, useEffect, useMemo, useState } from 'react'
import { APIProvider, Map, useMap, useMapsLibrary } from '@vis.gl/react-google-maps'

const API_KEY =
  import.meta.env.VITE_GOOGLE_CLOUD_API_KEY ||
  import.meta.env.VITE_GOOGLE_MAPS_API_KEY ||
  import.meta.env.GOOGLE_JS_API_KEY

const DAY_COLORS = ['#0A192F', '#D4AF37', '#7c3aed', '#0f766e', '#be123c']

function travelModeFromPreference(preference) {
  switch (preference) {
    case 'driving':
      return 'DRIVING'
    case 'transit':
      return 'TRANSIT'
    case 'walking':
      return 'WALKING'
    default:
      return 'WALKING'
  }
}

function formatKm(meters) {
  if (!meters) return '0 m'
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m`
}

function formatDuration(seconds) {
  if (!seconds) return '0 min'
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}

function Polyline({ path, strokeColor = '#0A192F', strokeOpacity = 0.9, strokeWeight = 5 }) {
  const map = useMap()
  const [polyline, setPolyline] = useState(null)

  useEffect(() => {
    if (!map || !window.google?.maps || !path?.length) return

    const poly = new window.google.maps.Polyline({
      path,
      strokeColor,
      strokeOpacity,
      strokeWeight,
      geodesic: false,
    })
    poly.setMap(map)
    setPolyline(poly)

    return () => {
      poly.setMap(null)
    }
  }, [map, strokeColor, strokeOpacity, strokeWeight])

  useEffect(() => {
    if (polyline && path) polyline.setPath(path)
  }, [polyline, path])

  return null
}

function LegacyMarker({ position, title, labelText, onClick, isActive, fillColor }) {
  const map = useMap()
  const [marker, setMarker] = useState(null)
  const [infoWindow, setInfoWindow] = useState(null)

  useEffect(() => {
    if (!map || !window.google?.maps) return

    const m = new window.google.maps.Marker({
      position,
      map,
      title,
      label: {
        text: labelText,
        color: '#FFFFFF',
        fontWeight: 'bold',
        fontSize: '13px',
        fontFamily: "'Inter', sans-serif",
      },
      icon: {
        path: window.google.maps.SymbolPath.CIRCLE,
        scale: 14,
        fillColor: fillColor || '#0A192F',
        fillOpacity: 1,
        strokeColor: '#D4AF37',
        strokeWeight: 2.5,
      },
    })
    setMarker(m)

    let listener = null
    if (onClick) listener = m.addListener('click', onClick)

    return () => {
      if (listener) listener.remove()
      m.setMap(null)
    }
  }, [map, onClick, position, title, labelText, fillColor])

  useEffect(() => {
    if (!marker || !window.google?.maps) return

    const iw = new window.google.maps.InfoWindow({
      content: `<div class="custom-info-window">${title}</div>`,
      disableAutoPan: true,
    })
    setInfoWindow(iw)

    return () => {
      iw.close()
    }
  }, [marker, title])

  useEffect(() => {
    if (!infoWindow || !marker || !map) return
    if (isActive) {
      infoWindow.open({ anchor: marker, map })
    } else {
      infoWindow.close()
    }
  }, [isActive, infoWindow, marker, map])

  return null
}

function BoundsController({ stops }) {
  const map = useMap()
  const coreLib = useMapsLibrary('core')

  useEffect(() => {
    if (!map || !stops?.length || !coreLib) return

    const bounds = new coreLib.LatLngBounds()
    stops.forEach((stop) => {
      if (typeof stop.lat === 'number' && typeof stop.lng === 'number') {
        bounds.extend({ lat: stop.lat, lng: stop.lng })
      }
    })
    
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, 64)
    }
  }, [map, stops, coreLib])

  return null
}

function MapPanController({ activeStopId, stops }) {
  const map = useMap()
  const coreLib = useMapsLibrary('core')

  useEffect(() => {
    if (!map || !activeStopId || !stops?.length || !coreLib) return
    const stop = stops.find((s) => String(s.id) === String(activeStopId))
    if (stop && typeof stop.lat === 'number' && typeof stop.lng === 'number') {
      map.panTo({ lat: stop.lat, lng: stop.lng })
    }
  }, [map, activeStopId, stops, coreLib])

  return null
}

function pathFromDirectionsResult(result) {
  const overview = result?.routes?.[0]?.overview_path
  if (!overview?.length) return null
  return overview.map((point) => ({ lat: point.lat(), lng: point.lng() }))
}

function PerDayRoadRoutes({ days, travelMode, onStatsChange }) {
  const map = useMap()
  const [routesByDay, setRoutesByDay] = useState({})
  const [calculating, setCalculating] = useState(false)
  const [routeError, setRouteError] = useState(null)

  useEffect(() => {
    if (!map || !window.google?.maps || days.length === 0) {
      setRoutesByDay({})
      onStatsChange?.({ calculating: false, routeError: null, totals: [] })
      return
    }

    let cancelled = false
    const service = new window.google.maps.DirectionsService()
    setCalculating(true)
    setRouteError(null)
    onStatsChange?.({ calculating: true, routeError: null, totals: [] })

    const mode = window.google.maps.TravelMode[travelMode] || window.google.maps.TravelMode.WALKING

    const requests = days.map((day) => {
      const stops = [...(day.stops ?? [])].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))

      if (stops.length < 2) {
        return Promise.resolve({
          dayNumber: day.dayNumber,
          path: null,
          orderedStops: stops,
          distanceText: null,
          durationText: null,
        })
      }

      const origin = { lat: stops[0].lat, lng: stops[0].lng }
      const destination = { lat: stops[stops.length - 1].lat, lng: stops[stops.length - 1].lng }
      const middle = stops.slice(1, -1).slice(0, 25)

      return new Promise((resolve) => {
        service.route(
          {
            origin,
            destination,
            waypoints: middle.map((s) => ({
              location: { lat: s.lat, lng: s.lng },
              stopover: true,
            })),
            travelMode: mode,
            provideRouteAlternatives: false,
          },
          (result, status) => {
            if (status !== window.google.maps.DirectionsStatus.OK) {
              console.error(`Directions failed for day ${day.dayNumber}:`, status)
              resolve({
                dayNumber: day.dayNumber,
                path: null,
                orderedStops: stops,
                error: status,
              })
              return
            }

            const legs = result.routes[0]?.legs ?? []
            const meters = legs.reduce((sum, leg) => sum + (leg.distance?.value ?? 0), 0)
            const seconds = legs.reduce((sum, leg) => sum + (leg.duration?.value ?? 0), 0)

            resolve({
              dayNumber: day.dayNumber,
              path: pathFromDirectionsResult(result),
              orderedStops: stops,
              distanceText: formatKm(meters),
              durationText: formatDuration(seconds),
            })
          }
        )
      })
    })

    Promise.all(requests).then((results) => {
      if (cancelled) return

      const byDay = {}
      let anyError = null
      results.forEach((entry) => {
        byDay[entry.dayNumber] = entry
        if (entry.error) anyError = entry.error
      })

      setRoutesByDay(byDay)
      setRouteError(anyError)
      setCalculating(false)

      const totals = results
        .filter((entry) => entry.path)
        .map((entry) => ({
          dayNumber: entry.dayNumber,
          distance: entry.distanceText,
          duration: entry.durationText,
        }))

      onStatsChange?.({ calculating: false, routeError: anyError, totals })

      if (window.google?.maps) {
        const bounds = new window.google.maps.LatLngBounds()
        results.forEach((entry) =>
          entry.orderedStops.forEach((stop) => {
            if (typeof stop.lat === 'number' && typeof stop.lng === 'number') {
              bounds.extend({ lat: stop.lat, lng: stop.lng })
            }
          })
        )
        if (!bounds.isEmpty()) {
          map.fitBounds(bounds, 64)
        }
      }
    })

    return () => {
      cancelled = true
    }
  }, [map, days, travelMode, onStatsChange])

  return (
    <>
      {Object.values(routesByDay).map((entry, index) =>
        entry.path?.length > 1 ? (
          <Polyline
            key={`route-day-${entry.dayNumber}`}
            path={entry.path}
            strokeColor={DAY_COLORS[index % DAY_COLORS.length]}
          />
        ) : null
      )}
    </>
  )
}

function RouteSummaryPanel({ calculating, routeError, totals, totalWalkMin }) {
  return (
    <div
      className="absolute top-6 right-6 bg-surface/90 backdrop-blur-md rounded-2xl p-4 border border-outline-variant/20 flex flex-col gap-2 max-w-xs z-10"
      style={{ boxShadow: 'var(--shadow-raised)' }}
    >
      <h3
        className="text-lg font-semibold text-primary leading-tight"
        style={{ fontFamily: 'var(--font-display)' }}
      >
        Total Route
      </h3>

      {calculating && (
        <div className="text-xs text-on-surface-muted font-semibold uppercase tracking-wider">
          Calculating route…
        </div>
      )}

      {!calculating && routeError && (
        <div className="text-xs text-red-700 font-semibold" style={{ fontFamily: 'var(--font-body)' }}>
          Couldn&apos;t route one or more days ({routeError}). Check that every stop has valid coordinates.
        </div>
      )}

      {!calculating &&
        totals?.map((entry) => (
          <div
            key={entry.dayNumber}
            className="text-xs text-on-surface-muted font-semibold uppercase tracking-wider"
            style={{ fontFamily: 'var(--font-body)' }}
          >
            Day {entry.dayNumber}: {entry.distance} · {entry.duration}
          </div>
        ))}

      {!calculating && totalWalkMin > 0 && (
        <div
          className="flex items-center gap-2 text-on-surface-muted text-xs font-semibold uppercase tracking-wider border-t border-outline-variant/20 pt-2 mt-1"
          style={{ fontFamily: 'var(--font-body)' }}
        >
          <span className="material-symbols-outlined text-[16px]">directions_walk</span>
          {totalWalkMin} min walking total
        </div>
      )}
    </div>
  )
}

function MapLayers({
  days,
  travelMode,
  onPinClick,
  activeStopId,
  totalWalkMin,
  destination,
}) {
  const map = useMap()
  const geocodingLib = useMapsLibrary('geocoding')
  const allStops = useMemo(
    () => days.flatMap((day) => day.stops ?? []),
    [days]
  )

  const [routeStats, setRouteStats] = useState({
    calculating: false,
    routeError: null,
    totals: [],
  })

  const handleStatsChange = useCallback((stats) => {
    setRouteStats(stats)
  }, [])

  const [geocodedCenter, setGeocodedCenter] = useState(null)
  const [clickedPlaceId, setClickedPlaceId] = useState(null)

  const handleMapClick = useCallback((e) => {
    const placeId = e.detail?.placeId
    if (placeId) {
      if (placeId === clickedPlaceId) {
        // Stop default info window from re-opening if it's the same POI
        e.stop()
        setClickedPlaceId(null)
      } else {
        setClickedPlaceId(placeId)
      }
    } else {
      setClickedPlaceId(null)
    }
  }, [clickedPlaceId])

  useEffect(() => {
    if (allStops.length > 0 || !geocodingLib || !destination) return
    let cancelled = false
    const geocoder = new geocodingLib.Geocoder()
    geocoder.geocode({ address: destination }, (results, status) => {
      if (cancelled || status !== 'OK' || !results?.[0]?.geometry?.location) return
      setGeocodedCenter({
        lat: results[0].geometry.location.lat(),
        lng: results[0].geometry.location.lng(),
      })
    })
    return () => {
      cancelled = true
    }
  }, [allStops.length, geocodingLib, destination])

  useEffect(() => {
    if (!map) return
    if (allStops.length > 0) {
      // BoundsController will handle zooming when stops exist
      return
    }
    if (geocodedCenter) {
      map.setCenter(geocodedCenter)
      map.setZoom(12)
    } else {
      map.setCenter({ lat: 43.6532, lng: -79.3832 }) // Fallback to Toronto instead of Bogota
      map.setZoom(12)
    }
  }, [map, allStops.length, geocodedCenter])

  // Initial render center
  const defaultCenter =
    allStops.length > 0
      ? { lat: allStops[0].lat, lng: allStops[0].lng }
      : { lat: 43.6532, lng: -79.3832 } // Fallback to Toronto

  return (
    <>
      <Map
        defaultCenter={defaultCenter}
        defaultZoom={allStops.length > 0 ? 13 : 12}
        disableDefaultUI={true}
        zoomControl={true}
        gestureHandling="greedy"
        style={{ width: '100%', height: '100%' }}
        onClick={handleMapClick}
      >
        {allStops.length > 0 && <BoundsController stops={allStops} />}
        <MapPanController activeStopId={activeStopId} stops={allStops} />
        <PerDayRoadRoutes days={days} travelMode={travelMode} onStatsChange={handleStatsChange} />

        {days.map((day, dayIndex) => {
          const color = DAY_COLORS[dayIndex % DAY_COLORS.length]
          const ordered = [...(day.stops ?? [])].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
          return ordered.map((stop, idx) => (
            <LegacyMarker
              key={`${day.dayNumber}-${stop.id}`}
              position={{ lat: stop.lat, lng: stop.lng }}
              onClick={() => onPinClick?.(stop.id)}
              title={stop.name || `Stop ${idx + 1}`}
              labelText={String(idx + 1)}
              isActive={String(activeStopId) === String(stop.id)}
              fillColor={color}
            />
          ))
        })}
      </Map>

      <RouteSummaryPanel
        calculating={routeStats.calculating}
        routeError={routeStats.routeError}
        totals={routeStats.totals}
        totalWalkMin={totalWalkMin}
      />
    </>
  )
}

/**
 * MapRoute — one road-following polyline per day (avoids cross-day straight lines).
 *
 * days: [{ dayNumber, stops: [{ id, name, lat, lng, order }] }]
 */
export default function MapRoute({
  days = [],
  travelMode = 'WALKING',
  onPinClick,
  activeStopId = null,
  totalWalkMin = 0,
  destination = '',
}) {
  if (!API_KEY) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-container">
        <p className="text-on-surface-muted text-sm">
          Map unavailable — set `VITE_GOOGLE_CLOUD_API_KEY`.
        </p>
      </div>
    )
  }

  return (
    <APIProvider apiKey={API_KEY}>
      <div className="relative w-full h-full">
        <MapLayers
          days={days}
          travelMode={travelMode}
          onPinClick={onPinClick}
          activeStopId={activeStopId}
          totalWalkMin={totalWalkMin}
          destination={destination}
        />
      </div>
    </APIProvider>
  )
}

export { travelModeFromPreference }
