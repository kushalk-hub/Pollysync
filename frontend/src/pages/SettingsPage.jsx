import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import InteractiveGoogleMap from "../components/InteractiveGoogleMap";
import Select from "../components/Select";
import { useFarm } from "../context/FarmContext";
import { useToast } from "../context/ToastContext";
import { reverseGeocode, searchLocations } from "../lib/location";
import { getNotificationPreferences, updateFarm, updateNotificationPreferences } from "../lib/api";

const TABS = [
  { key: "general", label: "Farm settings", icon: "agriculture" },
  { key: "alerts", label: "Notifications", icon: "notifications_active" },
];

const CROP_OPTIONS = [
  { value: "Mustard", label: "Mustard", icon: "eco" },
  { value: "Sunflower", label: "Sunflower", icon: "local_florist" },
  { value: "Cotton", label: "Cotton", icon: "filter_drama" },
];

const SOIL_TYPES = [
  { value: "loamy", label: "Loamy" }, { value: "alluvial", label: "Alluvial" },
  { value: "black", label: "Black soil (Regur)" }, { value: "red", label: "Red and yellow" },
  { value: "laterite", label: "Laterite" }, { value: "sandy", label: "Sandy" }, { value: "clay", label: "Clay" },
];

const IRRIGATION_OPTIONS = [
  { value: "drip", label: "Drip irrigation" }, { value: "sprinkler", label: "Sprinkler" },
  { value: "flood", label: "Flood irrigation" }, { value: "rainfed", label: "Rainfed" },
];

function farmToForm(farm) {
  return {
    farmName: farm?.name || "", crop: farm?.crop_type || "", variety: farm?.variety || "",
    irrigationMethod: farm?.irrigation_method || "", plantingDate: farm?.planting_date || "",
    harvestDate: farm?.harvest_date || "", location: farm?.location_name || "",
    lat: farm?.location_lat ?? null, lng: farm?.location_lng ?? null,
    acreage: farm?.area_acres != null ? String(farm.area_acres) : "", soilType: farm?.soil_type || "",
  };
}

function sameRelevantSettings(before, after) {
  return ["crop", "plantingDate", "harvestDate", "location", "lat", "lng"].every((key) => String(before[key] ?? "") === String(after[key] ?? ""));
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { selectedFarm, selectedFarmId, loadingFarms, refreshFarms } = useFarm();
  const [tab, setTab] = useState("general");
  const [form, setForm] = useState(() => farmToForm(null));
  const [savedForm, setSavedForm] = useState(() => farmToForm(null));
  const [saving, setSaving] = useState(false);
  const [locating, setLocating] = useState(false);
  const [locationResults, setLocationResults] = useState([]);
  const [showRunPrompt, setShowRunPrompt] = useState(false);
  const [notifications, setNotifications] = useState({ pushCritical: true, pushDaily: true, pushSystem: false, emailWeekly: true, emailBilling: true, whatsappUrgent: false, smsAlerts: true });

  useEffect(() => {
    const next = farmToForm(selectedFarm);
    setForm(next);
    setSavedForm(next);
    setShowRunPrompt(false);
  }, [selectedFarmId, selectedFarm]);

  useEffect(() => {
    let active = true;
    getNotificationPreferences().then((data) => {
      if (!active) return;
      setNotifications({ pushCritical: data.push_critical, pushDaily: data.push_daily, pushSystem: data.push_system, emailWeekly: data.email_weekly, emailBilling: data.email_billing, whatsappUrgent: data.whatsapp_urgent, smsAlerts: data.sms_alerts });
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const query = form.location.trim();
    if (query.length < 3 || (selectedFarm?.location_name || "") === query) {
      setLocationResults([]);
      return undefined;
    }
    const timer = window.setTimeout(() => {
      searchLocations(query).then(setLocationResults).catch(() => setLocationResults([]));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [form.location, selectedFarm?.location_name]);

  const mapCenter = useMemo(() => form.lat != null && form.lng != null ? { lat: Number(form.lat), lng: Number(form.lng) } : { lat: 19.9975, lng: 73.7898 }, [form.lat, form.lng]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  async function applyCoordinates(coords, preferredName = "") {
    setLocating(true);
    try {
      const resolved = preferredName ? { address: preferredName } : await reverseGeocode(coords.lat, coords.lng);
      setForm((current) => ({ ...current, lat: coords.lat, lng: coords.lng, location: resolved.address }));
      setLocationResults([]);
    } catch {
      setForm((current) => ({ ...current, lat: coords.lat, lng: coords.lng, location: preferredName || current.location || "Selected location" }));
      toast.error("Coordinates were updated, but the place name could not be found.");
    } finally {
      setLocating(false);
    }
  }

  function detectLocation() {
    if (!navigator.geolocation) {
      toast.error("Geolocation is not supported by this browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => applyCoordinates({ lat: position.coords.latitude, lng: position.coords.longitude }),
      () => { setLocating(false); toast.error("Unable to access your current location. Check browser location permissions."); },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  }

  async function handleSave(event) {
    event.preventDefault();
    if (tab === "general" && (!selectedFarmId || !form.farmName.trim() || !form.crop)) {
      toast.error("Farm name and crop are required.");
      return;
    }
    setSaving(true);
    try {
      if (tab === "alerts") {
        await updateNotificationPreferences({ push_critical: notifications.pushCritical, push_daily: notifications.pushDaily, push_system: notifications.pushSystem, email_weekly: notifications.emailWeekly, email_billing: notifications.emailBilling, whatsapp_urgent: notifications.whatsappUrgent, sms_alerts: notifications.smsAlerts });
        toast.success("Notification preferences saved.");
      } else {
        await updateFarm(selectedFarmId, {
          name: form.farmName.trim(), crop_type: form.crop, variety: form.variety || null,
          irrigation_method: form.irrigationMethod || null, planting_date: form.plantingDate || null,
          harvest_date: form.harvestDate || null, location_name: form.location.trim() || null,
          location_lat: form.lat, location_lng: form.lng,
          area_acres: form.acreage ? Number(form.acreage) : null, soil_type: form.soilType || null,
        });
        const requiresPrediction = !sameRelevantSettings(savedForm, form);
        await refreshFarms();
        setSavedForm(form);
        setShowRunPrompt(requiresPrediction);
        toast.success(requiresPrediction ? "Farm saved. Run a new prediction to refresh your results." : "Farm settings saved.");
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Could not save your changes.");
    } finally {
      setSaving(false);
    }
  }

  if (loadingFarms) return <div className="p-lg text-body-md text-on-surface-variant">Loading farm settings…</div>;
  if (!selectedFarm) return <div className="rounded-2xl border border-outline-variant bg-surface p-xl text-center"><h1 className="text-headline-md font-headline-md">No farm selected</h1><p className="mt-sm text-body-md text-on-surface-variant">Create a farm before configuring crop settings.</p><button onClick={() => navigate("/farms?new=1")} className="mt-lg min-h-11 rounded-lg bg-primary px-lg font-bold text-on-primary">Go to My Farms</button></div>;

  return (
    <div className="mx-auto max-w-7xl space-y-lg pb-28">
      <header>
        <p className="text-label-sm font-bold uppercase tracking-wide text-primary">Selected farm</p>
        <h1 className="mt-1 text-headline-lg font-headline-lg text-on-surface">Farm settings</h1>
        <p className="mt-1 text-body-md text-on-surface-variant">Update {selectedFarm.name}; new predictions will use these details.</p>
      </header>

      {showRunPrompt && <section className="flex flex-col gap-md rounded-2xl border border-secondary/40 bg-secondary-container/10 p-lg sm:flex-row sm:items-center sm:justify-between"><div className="flex gap-sm"><span className="material-symbols-outlined text-secondary">update</span><div><h2 className="font-label-md text-on-surface">Prediction needs an update</h2><p className="mt-1 text-body-sm text-on-surface-variant">Your crop, planting date, or location changed. Existing results remain in history.</p></div></div><button onClick={() => navigate(`/predict?farm_id=${selectedFarmId}`)} className="min-h-11 rounded-lg bg-primary px-lg text-label-md font-bold text-on-primary">Run new prediction</button></section>}

      <div role="tablist" aria-label="Settings sections" className="flex gap-sm overflow-x-auto border-b border-outline-variant">
        {TABS.map((item) => <button key={item.key} role="tab" aria-selected={tab === item.key} onClick={() => setTab(item.key)} className={`min-h-11 shrink-0 border-b-2 px-md text-label-md ${tab === item.key ? "border-primary font-bold text-primary" : "border-transparent text-on-surface-variant"}`}><span className="material-symbols-outlined mr-xs align-middle text-[18px]">{item.icon}</span>{item.label}</button>)}
      </div>

      <form onSubmit={handleSave}>
        {tab === "general" ? <div className="grid gap-lg lg:grid-cols-12">
          <section className="rounded-2xl border border-outline-variant bg-surface p-lg shadow-sm lg:col-span-7">
            <div className="mb-lg"><h2 className="text-headline-md font-headline-md">Farm identity & location</h2><p className="mt-1 text-body-sm text-on-surface-variant">Map, GPS, and search always save the location name with its coordinates.</p></div>
            <div className="grid gap-md sm:grid-cols-2"><Field label="Farm name"><input required value={form.farmName} onChange={(event) => update("farmName", event.target.value)} className="input-base" /></Field><Field label="Location search"><div className="relative"><input value={form.location} onChange={(event) => update("location", event.target.value)} placeholder="Search a town, village, or district" className="input-base pr-24" /><button type="button" onClick={detectLocation} disabled={locating} className="absolute right-1 top-1 min-h-9 rounded-md px-sm text-label-sm font-bold text-primary hover:bg-surface-container">{locating ? "Finding…" : "Use GPS"}</button>{locationResults.length > 0 && <div className="absolute z-20 mt-1 w-full rounded-lg border border-outline-variant bg-surface p-1 shadow-lg">{locationResults.map((result) => <button key={result.id} type="button" onClick={() => applyCoordinates(result, result.name)} className="w-full rounded-md px-sm py-sm text-left text-body-sm text-on-surface hover:bg-surface-container">{result.name}</button>)}</div>}</div></Field></div>
            <div className="mt-lg h-72 overflow-hidden rounded-xl border border-outline-variant"><InteractiveGoogleMap center={mapCenter} zoom={10} onLocationSelect={applyCoordinates} /></div>
            <div className="mt-md grid gap-sm rounded-xl bg-surface-container p-md sm:grid-cols-2"><p className="text-body-sm text-on-surface-variant"><strong className="text-on-surface">Coordinates: </strong>{form.lat != null ? `${Number(form.lat).toFixed(4)}° N` : "—"}, {form.lng != null ? `${Number(form.lng).toFixed(4)}° E` : "—"}</p><p className="truncate text-body-sm text-on-surface-variant"><strong className="text-on-surface">Saved location: </strong>{form.location || "—"}</p></div>
          </section>
          <div className="space-y-lg lg:col-span-5"><section className="rounded-2xl border border-outline-variant bg-surface p-lg shadow-sm"><h2 className="text-headline-md font-headline-md">Crop settings</h2><div className="mt-lg space-y-md"><Select label="Crop" value={form.crop} onChange={(value) => update("crop", value)} options={CROP_OPTIONS} placeholder="Choose a crop" /><Field label="Variety / cultivar"><input value={form.variety} onChange={(event) => update("variety", event.target.value)} className="input-base" placeholder="Optional" /></Field><div className="grid gap-md sm:grid-cols-2"><Field label="Planting date"><input type="date" value={form.plantingDate} onChange={(event) => update("plantingDate", event.target.value)} className="input-base" /></Field><Field label="Expected harvest"><input type="date" min={form.plantingDate || undefined} value={form.harvestDate} onChange={(event) => update("harvestDate", event.target.value)} className="input-base" /></Field></div></div></section><section className="rounded-2xl border border-outline-variant bg-surface p-lg shadow-sm"><h2 className="text-headline-md font-headline-md">Production details</h2><div className="mt-lg grid gap-md sm:grid-cols-2"><Field label="Total acreage (acres)"><input type="number" min="0" step="0.1" value={form.acreage} onChange={(event) => update("acreage", event.target.value)} className="input-base" /></Field><Select label="Soil type" value={form.soilType} onChange={(value) => update("soilType", value)} options={SOIL_TYPES} placeholder="Select soil type" /><div className="sm:col-span-2"><Select label="Irrigation method" value={form.irrigationMethod} onChange={(value) => update("irrigationMethod", value)} options={IRRIGATION_OPTIONS} placeholder="Select irrigation method" /></div></div></section></div>
        </div> : <NotificationSettings notifications={notifications} setNotifications={setNotifications} />}
        <footer className="fixed inset-x-0 bottom-0 z-30 border-t border-outline-variant bg-surface/95 p-md backdrop-blur lg:left-64"><div className="mx-auto flex max-w-7xl justify-end gap-sm"><button type="button" onClick={() => { setForm(savedForm); setShowRunPrompt(false); }} className="min-h-11 rounded-lg px-lg text-label-md font-bold text-on-surface-variant">Discard</button><button type="submit" disabled={saving} className="min-h-11 rounded-lg bg-primary px-lg text-label-md font-bold text-on-primary disabled:opacity-60">{saving ? "Saving…" : tab === "alerts" ? "Save notifications" : "Save farm settings"}</button></div></footer>
      </form>
    </div>
  );
}

function Field({ label, children }) { return <label className="block text-label-md text-on-surface-variant"><span className="mb-sm block">{label}</span>{children}</label>; }

function NotificationSettings({ notifications, setNotifications }) {
  const items = [["pushCritical", "Critical risk alerts", "Receive urgent pollination-risk updates."], ["pushDaily", "Daily summary", "Receive the daily field outlook."], ["pushSystem", "System updates", "Receive product and maintenance updates."], ["emailWeekly", "Weekly email report", "Receive a weekly performance report."], ["smsAlerts", "SMS alerts", "Receive time-sensitive alerts by SMS."]];
  return <section className="max-w-3xl rounded-2xl border border-outline-variant bg-surface p-lg shadow-sm"><h2 className="text-headline-md font-headline-md">Notifications</h2><p className="mt-1 text-body-sm text-on-surface-variant">Choose how PolliSync should contact you.</p><div className="mt-lg divide-y divide-outline-variant">{items.map(([key, title, description]) => <label key={key} className="flex min-h-16 cursor-pointer items-center justify-between gap-lg py-md"><span><span className="block text-label-md font-bold text-on-surface">{title}</span><span className="mt-1 block text-body-sm text-on-surface-variant">{description}</span></span><input type="checkbox" checked={notifications[key]} onChange={() => setNotifications((current) => ({ ...current, [key]: !current[key] }))} className="h-5 w-5 accent-primary" /></label>)}</div></section>;
}
