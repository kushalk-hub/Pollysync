import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { applyMaharashtraBounds } from "../lib/geo";

function calculateBounds(centerLat, centerLng, radiusKm) {
  const latDelta = radiusKm / 111.32;
  const lngDelta = radiusKm / (111.32 * Math.cos((centerLat * Math.PI) / 180));
  return [
    [centerLat - latDelta, centerLng - lngDelta],
    [centerLat + latDelta, centerLng + lngDelta],
  ];
}

export default function InteractiveGoogleMap({
  center,
  zoom = 12,
  onLocationSelect,
  district = null,
}) {
  const mapRef = useRef(null);
  const leafletMapRef = useRef(null);
  const leafletMarkerRef = useRef(null);
  const leafletCircleRef = useRef(null);
  const onLocationSelectRef = useRef(onLocationSelect);

  useEffect(() => {
    onLocationSelectRef.current = onLocationSelect;
  }, [onLocationSelect]);

  function syncDistrict(map, nextDistrict) {
    if (leafletCircleRef.current) {
      map.removeLayer(leafletCircleRef.current);
      leafletCircleRef.current = null;
    }

    applyMaharashtraBounds(map);

    if (!nextDistrict || !nextDistrict.radius_km) return;

    const bounds = calculateBounds(
      nextDistrict.centroid_lat,
      nextDistrict.centroid_lng,
      nextDistrict.radius_km
    );
    map.setMaxBounds(bounds);
    map.setMinZoom(11);
    map.setMaxZoom(16);

    leafletCircleRef.current = L.circle(
      [nextDistrict.centroid_lat, nextDistrict.centroid_lng],
      {
        radius: nextDistrict.radius_km * 1000,
        color: "#10b981",
        fillColor: "#10b981",
        fillOpacity: 0.05,
        weight: 2,
        dashArray: "5,5",
      }
    ).addTo(map);
  }

  // Single effect: init when center becomes available, update marker/constraints when center or district changes after init
  useEffect(() => {
    if (!mapRef.current || !center) return;

    // Map already initialized — update marker, district constraints, then move the view
    if (leafletMapRef.current && leafletMarkerRef.current) {
      leafletMarkerRef.current.setLatLng([center.lat, center.lng]);
      syncDistrict(leafletMapRef.current, district);
      leafletMapRef.current.setView(
        [center.lat, center.lng],
        district ? 13 : leafletMapRef.current.getZoom()
      );
      return;
    }

    // Map not yet initialized and center is available — init
    if (leafletMapRef.current) return;

    const timer = setTimeout(() => {
      if (!mapRef.current || leafletMapRef.current) return;

      mapRef.current.innerHTML = "";

      const map = L.map(mapRef.current, {
        zoomControl: true,
        attributionControl: true,
      }).setView([center.lat, center.lng], zoom);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      const blueIcon = L.icon({
        iconUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41],
      });

      const marker = L.marker([center.lat, center.lng], {
        icon: blueIcon,
        draggable: true,
      }).addTo(map);

      marker.bindPopup("Click map or drag marker to set location").openPopup();

      marker.on("dragend", () => {
        const pos = marker.getLatLng();
        if (onLocationSelectRef.current) {
          onLocationSelectRef.current({ lat: pos.lat, lng: pos.lng });
        }
      });

      map.on("click", (e) => {
        marker.setLatLng(e.latlng);
        marker.openPopup();
        if (onLocationSelectRef.current) {
          onLocationSelectRef.current({ lat: e.latlng.lat, lng: e.latlng.lng });
        }
      });

      leafletMapRef.current = map;
      leafletMarkerRef.current = marker;

      syncDistrict(map, district);

      setTimeout(() => map.invalidateSize(), 200);
    }, 50);

    return () => clearTimeout(timer);
  }, [center, zoom, district]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (leafletMapRef.current) {
        leafletMapRef.current.remove();
        leafletMapRef.current = null;
      }
    };
  }, []);

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-outline-variant bg-surface-container-higher" style={{ minHeight: 200 }}>
      <div ref={mapRef} className="w-full h-full" style={{ minHeight: 200 }} />
    </div>
  );
}
