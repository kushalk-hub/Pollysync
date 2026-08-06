import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";
import { applyMaharashtraBounds } from "../lib/geo";

export default function BeeMap({ center = [20, 78], occurrences = [], zoom = 8, farmName = "Farm", crop = "", psiScore }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef([]);

  useEffect(() => {
    async function init() {
      const L = await import("leaflet");

      if (!mapInstance.current && mapRef.current) {
        const map = L.map(mapRef.current).setView(center, zoom);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        }).addTo(map);
        applyMaharashtraBounds(map);
        mapInstance.current = map;
      }
    }

    init();

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, []);

  // Update map view when farm center changes dynamically
  useEffect(() => {
    if (mapInstance.current && center && center[0] && center[1]) {
      mapInstance.current.setView(center, mapInstance.current.getZoom());
    }
  }, [center]);

  // Automatically center on browser GPS location on mount if coordinates are default
  useEffect(() => {
    if (navigator.geolocation && center && center[0] === 20 && center[1] === 78) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const userCenter = [position.coords.latitude, position.coords.longitude];
          if (mapInstance.current) {
            mapInstance.current.setView(userCenter, mapInstance.current.getZoom());
          }
        },
        (err) => console.log("Automatic dashboard geolocation skipped:", err),
        { enableHighAccuracy: true, timeout: 5000 }
      );
    }
  }, []);

  useEffect(() => {
    async function addMarkers() {
      const L = await import("leaflet");
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      if (!mapInstance.current) return;

      const redIcon = L.icon({
        iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-red.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41],
      });

      const blueIcon = L.icon({
        iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41],
      });

      // Add Farm Location marker (blue)
      if (center && center[0] && center[1]) {
        const farmMarker = L.marker(center, { icon: blueIcon })
          .addTo(mapInstance.current)
          .bindPopup(`<b>${farmName}</b>${crop ? `<br/>${crop}` : ""}${psiScore != null ? `<br/>PSI: ${psiScore}/100` : ""}`)
          .openPopup();
        markersRef.current.push(farmMarker);
      }

      // Add Bee Occurrences markers (red)
      occurrences.forEach((occ) => {
        const marker = L.marker([occ.lat, occ.lng], { icon: redIcon })
          .addTo(mapInstance.current)
          .bindPopup(`<b>${occ.species}</b><br/>Bee Sighting`);
        markersRef.current.push(marker);
      });

      // Fit map bounds to show both the farm and all bee occurrences
      if (markersRef.current.length > 0) {
        const group = L.featureGroup(markersRef.current);
        mapInstance.current.fitBounds(group.getBounds().pad(0.15));
      }
    }

    addMarkers();
  }, [occurrences, center, farmName, crop, psiScore]);

  return (
    <div className="bg-surface border border-outline-variant rounded-xl overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.05)]">
      <div ref={mapRef} className="h-72 w-full" />
    </div>
  );
}
