import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import { useDistricts } from "../context/DistrictContext";
import { createFarm, updateProfile } from "../lib/api";
import InteractiveGoogleMap from "../components/InteractiveGoogleMap";
import DistrictSelector from "../components/DistrictSelector";

const CROPS = [
  { value: "Mustard", icon: "eco", desc: "Brassica juncea" },
  { value: "Wheat", icon: "grass", desc: "Triticum aestivum" },
  { value: "Sunflower", icon: "local_florist", desc: "Helianthus annuus" },
  { value: "Rice", icon: "water_drop", desc: "Oryza sativa" },
  { value: "Cotton", icon: "filter_drama", desc: "Gossypium" },
];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user, refreshUser, setOnboarded } = useAuth();
  const { getDistrictBySlug } = useDistricts();

  const [step, setStep] = useState(1);
  const [farmName, setFarmName] = useState("");
  const [districtSlug, setDistrictSlug] = useState("");
  const [customCoords, setCustomCoords] = useState(null);
  const [cropType, setCropType] = useState("");
  const [areaAcres, setAreaAcres] = useState("");
  const [soilType, setSoilType] = useState("");
  const [pesticideUsage, setPesticideUsage] = useState("");
  const [waterAvailability, setWaterAvailability] = useState("");
  const [plantingDate, setPlantingDate] = useState("");
  const [harvestDate, setHarvestDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedDistrict = getDistrictBySlug(districtSlug);

  useEffect(() => {
    if (user?.has_onboarded) {
      navigate("/dashboard");
    }
  }, [user, navigate]);

  // When district changes, set coords to centroid
  useEffect(() => {
    if (selectedDistrict) {
      setCustomCoords({
        lat: selectedDistrict.centroid_lat,
        lng: selectedDistrict.centroid_lng,
      });
    }
  }, [selectedDistrict]);

  const handleLocationSelect = useCallback((coords) => {
    setCustomCoords(coords);
  }, []);

  const handleDistrictChange = useCallback((slug) => {
    setDistrictSlug(slug);
    setError("");
  }, []);

  const handleSubmit = async () => {
    setError("");
    setLoading(true);

    try {
      if (!farmName || !districtSlug) {
        setError("Please fill in all required fields");
        setLoading(false);
        return;
      }

      const coords = customCoords || (selectedDistrict ? {
        lat: selectedDistrict.centroid_lat,
        lng: selectedDistrict.centroid_lng,
      } : null);

      if (!coords) {
        setError("Please select a district to set location");
        setLoading(false);
        return;
      }

      await createFarm({
        name: farmName,
        crop_type: cropType,
        district_slug: districtSlug,
        location_lat: coords.lat,
        location_lng: coords.lng,
        location_name: selectedDistrict?.name || districtSlug,
        area_acres: areaAcres ? parseFloat(areaAcres) : null,
        soil_type: soilType || null,
        pesticide_usage: pesticideUsage || null,
        water_availability: waterAvailability || null,
        planting_date: plantingDate || null,
        harvest_date: harvestDate || null,
      });

      await updateProfile({ has_onboarded: true });
      setOnboarded();

      toast.success("Farm created successfully! Welcome to PolliSync.");
      navigate("/dashboard");
    } catch (err) {
      const message = err?.response?.data?.detail || err.message || "Failed to create farm";
      toast.error(message);
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-md">
      <div className="w-full max-w-[640px]">
        {/* Header */}
        <div className="text-center mb-xl">
          <div className="flex items-center justify-center gap-sm mb-md">
            <span className="material-symbols-outlined text-primary text-[32px]">
              agriculture
            </span>
            <span className="font-headline-lg text-headline-lg text-primary font-bold">
              PolliSync
            </span>
          </div>
          <h1 className="font-headline-xl text-headline-xl text-on-background mb-xs">
            Welcome, {user?.full_name || "Farmer"}!
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Let's set up your first farm to get started with pollination predictions.
          </p>
        </div>

        {/* Progress Bar */}
        <div className="mb-xl flex items-center gap-sm">
          <div
            className={`h-2 flex-1 rounded-full transition-colors ${
              step >= 1 ? "bg-primary" : "bg-surface-container-high"
            }`}
          />
          <div
            className={`h-2 flex-1 rounded-full transition-colors ${
              step >= 2 ? "bg-primary" : "bg-surface-container-high"
            }`}
          />
          <div
            className={`h-2 flex-1 rounded-full transition-colors ${
              step >= 3 ? "bg-primary" : "bg-surface-container-high"
            }`}
          />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-lg bg-error-container p-4 text-body-sm font-medium text-on-error-container">
            {error}
          </div>
        )}

        {/* Step 1: Farm Name & District */}
        {step === 1 && (
          <div className="bg-surface border border-outline-variant rounded-xl p-xl shadow-sm">
            <h2 className="font-headline-md text-headline-md text-on-surface mb-lg">
              Farm Location
            </h2>
            <div className="space-y-lg">
              <div>
                <label className="block font-label-md text-label-md text-on-surface-variant mb-sm">
                  Farm Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g., North Field"
                  className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                  value={farmName}
                  onChange={(e) => setFarmName(e.target.value)}
                />
              </div>
              <DistrictSelector
                value={districtSlug}
                onChange={handleDistrictChange}
              />
              {selectedDistrict && (
                <div className="space-y-sm">
                  <p className="font-label-sm text-label-sm text-on-surface-variant">
                    Click on the map or drag the marker to set your farm's exact location
                  </p>
                  <div className="relative w-full h-[300px] rounded-xl overflow-hidden border border-outline-variant">
                    <InteractiveGoogleMap
                      center={customCoords || {
                        lat: selectedDistrict.centroid_lat,
                        lng: selectedDistrict.centroid_lng,
                      }}
                      zoom={13}
                      district={selectedDistrict}
                      onLocationSelect={handleLocationSelect}
                    />
                  </div>
                  {customCoords && (
                    <div className="flex gap-lg text-body-sm font-mono text-on-surface-variant">
                      <span>{customCoords.lat.toFixed(4)} N</span>
                      <span>{customCoords.lng.toFixed(4)} E</span>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="mt-xl flex justify-end">
              <button
                onClick={() => {
                  if (!farmName.trim()) {
                    setError("Please enter a farm name");
                    return;
                  }
                  if (!districtSlug) {
                    setError("Please select a district");
                    return;
                  }
                  setError("");
                  setStep(2);
                }}
                className="bg-primary hover:brightness-90 text-on-primary font-label-md text-label-md py-2 px-xl rounded-lg shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_1px_2px_rgba(0,0,0,0.1)] transition-all active:scale-[0.98] flex items-center gap-sm"
              >
                Next Step
                <span className="material-symbols-outlined text-[18px]">
                  arrow_forward
                </span>
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Crop Selection */}
        {step === 2 && (
          <div className="bg-surface border border-outline-variant rounded-xl p-xl shadow-sm">
            <button
              onClick={() => setStep(1)}
              className="flex items-center gap-sm text-on-surface-variant hover:text-primary transition-colors font-body-sm mb-lg"
            >
              <span className="material-symbols-outlined text-[18px]">
                arrow_back
              </span>
              Back to Location
            </button>
            <h2 className="font-headline-md text-headline-md text-on-surface mb-lg">
              Select Crop Type
            </h2>
            <div className="grid grid-cols-1 gap-md">
              {CROPS.map((item) => {
                const selected = cropType === item.value;
                return (
                  <label
                    key={item.value}
                    className="relative block cursor-pointer group"
                  >
                    <input
                      type="radio"
                      name="crop_selection"
                      className="peer sr-only"
                      checked={selected}
                      onChange={() => setCropType(item.value)}
                    />
                    <div
                      className={`bg-surface-container-high rounded-xl p-md flex items-center gap-md transition-all ${
                        selected
                          ? "border-2 border-primary shadow-[0_4px_12px_rgba(16,185,129,0.1)]"
                          : "border border-outline-variant hover:border-primary/50"
                      }`}
                    >
                      <div
                        className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          selected
                            ? "bg-primary text-on-primary"
                            : "bg-surface text-on-surface-variant"
                        }`}
                      >
                        <span className="material-symbols-outlined">
                          {item.icon}
                        </span>
                      </div>
                      <div className="flex-1">
                        <p className="font-label-lg text-label-lg text-on-surface">
                          {item.value}
                        </p>
                        <p className="text-body-sm text-on-surface-variant">
                          {item.desc}
                        </p>
                      </div>
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          selected
                            ? "border-primary bg-primary"
                            : "border-outline-variant"
                        }`}
                      >
                        {selected && (
                          <span className="material-symbols-outlined text-[14px] text-white">
                            check
                          </span>
                        )}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
            <div className="mt-xl flex justify-between">
              <button
                onClick={() => setStep(1)}
                className="px-md py-2 font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors"
              >
                Back
              </button>
              <button
                onClick={() => {
                  if (!cropType) {
                    setError("Please select a crop type");
                    return;
                  }
                  setError("");
                  setStep(3);
                }}
                className="bg-primary hover:brightness-90 text-on-primary font-label-md text-label-md py-2 px-xl rounded-lg shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_1px_2px_rgba(0,0,0,0.1)] transition-all active:scale-[0.98] flex items-center gap-sm"
              >
                Next Step
                <span className="material-symbols-outlined text-[18px]">
                  arrow_forward
                </span>
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Additional Details */}
        {step === 3 && (
          <div className="bg-surface border border-outline-variant rounded-xl p-xl shadow-sm">
            <button
              onClick={() => setStep(2)}
              className="flex items-center gap-sm text-on-surface-variant hover:text-primary transition-colors font-body-sm mb-lg"
            >
              <span className="material-symbols-outlined text-[18px]">
                arrow_back
              </span>
              Back to Crop Selection
            </button>
            <h2 className="font-headline-md text-headline-md text-on-surface mb-lg">
              Farm Details
            </h2>
            <div className="space-y-lg">
              <div>
                <label className="block font-label-md text-label-md text-on-surface-variant mb-sm">
                  Area (Acres)
                </label>
                <input
                  type="number"
                  placeholder="e.g., 5.5"
                  className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                  value={areaAcres}
                  onChange={(e) => setAreaAcres(e.target.value)}
                />
              </div>
              <div>
                <label className="block font-label-md text-label-md text-on-surface-variant mb-sm">
                  Soil Type
                </label>
                <select
                  className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                  value={soilType}
                  onChange={(e) => setSoilType(e.target.value)}
                >
                  <option value="">Select soil type</option>
                  <option value="clay">Clay</option>
                  <option value="sandy">Sandy</option>
                  <option value="loamy">Loamy</option>
                  <option value="silty">Silty</option>
                  <option value="peaty">Peaty</option>
                  <option value="chalky">Chalky</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="grid grid-cols-1 gap-md sm:grid-cols-2">
                <div>
                  <label className="block font-label-md text-label-md text-on-surface-variant mb-sm">
                    Pesticide Use <span className="font-body-sm text-body-sm">(optional)</span>
                  </label>
                  <select
                    className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                    value={pesticideUsage}
                    onChange={(e) => setPesticideUsage(e.target.value)}
                  >
                    <option value="">Not recorded</option>
                    <option value="none">None (pollinator-friendly)</option>
                    <option value="pre_flowering">Pre-flowering only</option>
                    <option value="during_flowering">During flowering</option>
                  </select>
                </div>
                <div>
                  <label className="block font-label-md text-label-md text-on-surface-variant mb-sm">
                    Water Availability <span className="font-body-sm text-body-sm">(optional)</span>
                  </label>
                  <select
                    className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                    value={waterAvailability}
                    onChange={(e) => setWaterAvailability(e.target.value)}
                  >
                    <option value="">Not recorded</option>
                    <option value="irrigated">Irrigated</option>
                    <option value="rainfed">Rainfed</option>
                    <option value="water_stressed">Water-stressed</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-md sm:grid-cols-2">
                <div>
                  <label className="block font-label-md text-label-md text-on-surface-variant mb-sm">
                    Planting Date <span className="font-body-sm text-body-sm">(optional)</span>
                  </label>
                  <input
                    type="date"
                    className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                    value={plantingDate}
                    onChange={(e) => setPlantingDate(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block font-label-md text-label-md text-on-surface-variant mb-sm">
                    Expected Harvest <span className="font-body-sm text-body-sm">(optional)</span>
                  </label>
                  <input
                    type="date"
                    className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-body-md text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
                    value={harvestDate}
                    onChange={(e) => setHarvestDate(e.target.value)}
                  />
                </div>
              </div>
              <p className="text-body-sm text-on-surface-variant">
                These dates are optional. When present, PolliSync uses them as farm settings to make flowering-window predictions more farm-specific.
              </p>
            </div>

            {/* Summary */}
            <div className="mt-xl p-md rounded-lg bg-surface-container-low border border-outline-variant/50">
              <h3 className="font-label-lg text-label-lg text-on-surface mb-sm">
                Summary
              </h3>
              <div className="space-y-xs text-body-sm text-on-surface-variant">
                <p>
                  <span className="font-medium text-on-surface">Farm:</span>{" "}
                  {farmName}
                </p>
                <p>
                  <span className="font-medium text-on-surface">District:</span>{" "}
                  {selectedDistrict?.name || districtSlug}
                </p>
                <p>
                  <span className="font-medium text-on-surface">Crop:</span>{" "}
                  {cropType}
                </p>
                {areaAcres && (
                  <p>
                    <span className="font-medium text-on-surface">Area:</span>{" "}
                    {areaAcres} acres
                  </p>
                )}
                {pesticideUsage && (
                  <p>
                    <span className="font-medium text-on-surface">Pesticide:</span>{" "}
                    {pesticideUsage.replace("_", " ")}
                  </p>
                )}
                {waterAvailability && (
                  <p>
                    <span className="font-medium text-on-surface">Water:</span>{" "}
                    {waterAvailability.replace("_", " ")}
                  </p>
                )}
                {plantingDate && (
                  <p>
                    <span className="font-medium text-on-surface">Planting:</span>{" "}
                    {plantingDate}
                  </p>
                )}
              </div>
            </div>

            <div className="mt-xl flex justify-between">
              <button
                onClick={() => setStep(2)}
                className="px-md py-2 font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors"
              >
                Back
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="bg-primary hover:brightness-90 text-on-primary font-label-md text-label-md py-2 px-xl rounded-lg shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_1px_2px_rgba(0,0,0,0.1)] transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-sm"
              >
                {loading ? (
                  <>
                    <span className="material-symbols-outlined text-[18px] animate-spin">
                      progress_activity
                    </span>
                    Creating Farm...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[18px]">
                      check
                    </span>
                    Create Farm & Start
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
