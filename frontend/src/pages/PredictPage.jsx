import { useState, useEffect, useRef } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import { useDistricts } from "../context/DistrictContext";
import { createPrediction, generateRecommendation, getFarms, getApiErrorMessage } from "../lib/api";
import InteractiveGoogleMap from "../components/InteractiveGoogleMap";
import DistrictSelector from "../components/DistrictSelector";
import { useFarm } from "../context/FarmContext";

const CROPS = [
  { value: "Mustard", icon: "eco", desc: "Brassica juncea. High sensitivity to temperature fluctuations during bloom.", bg: "bg-secondary-container/20", color: "text-secondary-container" },
  { value: "Sunflower", icon: "local_florist", desc: "Helianthus annuus. Highly dependent on bee activity and direct sunlight metrics.", bg: "bg-surface-container-high", color: "text-secondary" },
  { value: "Cotton", icon: "filter_drama", desc: "Gossypium. Complex pollination cycle requiring hybrid meteorological models.", bg: "bg-surface-container-high", color: "text-on-surface-variant" },
];

const LOADING_MESSAGES = [
  "Initiating Prediction Matrix...",
  "Fetching localized weather models...",
  "Analyzing historical bee populations...",
  "Cross-referencing farm topographies...",
  "Calculating pollination probabilities...",
  "Generating yield forecasts...",
  "Applying machine learning models...",
  "Finalizing prediction matrix...",
];

export default function PredictPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const { user } = useAuth();
  const { getDistrictBySlug } = useDistricts();
  const { selectedFarmId: globalFarmId, selectFarm } = useFarm();
  const [step, setStep] = useState(1);
  const [farms, setFarms] = useState([]);
  const [selectedFarmId, setSelectedFarmId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadMsgIndex, setLoadMsgIndex] = useState(0);
  const [error, setError] = useState("");
  const [loadingFarms, setLoadingFarms] = useState(true);

  const msgInterval = useRef(null);

  useEffect(() => {
    fetchFarms();
  }, []);

  async function fetchFarms() {
    try {
      setLoadingFarms(true);
      const data = await getFarms();
      setFarms(data);
      if (data.length > 0) {
        const requestedFarmId = searchParams.get("farm_id");
        const defaultFarm = data.find((f) => String(f.id) === String(requestedFarmId))
          || data.find((f) => String(f.id) === String(globalFarmId))
          || data.find((f) => f.is_default)
          || data[0];
        setSelectedFarmId(defaultFarm.id);
        selectFarm(defaultFarm.id);
      }
    } catch (err) {
      console.error("Failed to fetch farms:", err);
      setError("Failed to load farms. Please try again.");
    } finally {
      setLoadingFarms(false);
    }
  }

  useEffect(() => {
    if (loading) {
      msgInterval.current = setInterval(() => {
        setLoadMsgIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
      }, 3000);
    } else {
      clearInterval(msgInterval.current);
      setLoadMsgIndex(0);
    }
    return () => clearInterval(msgInterval.current);
  }, [loading]);

  async function handleSubmit() {
    setError("");
    setLoading(true);

    if (!selectedFarmId) {
      setError("Please select a farm");
      setLoading(false);
      return;
    }

    try {
      setLoadMsgIndex(0);
      selectFarm(selectedFarmId);
      const prediction = await createPrediction(selectedFarmId);

      setLoadMsgIndex(6);
      await generateRecommendation(selectedFarmId, prediction.id);

      toast.success("Prediction complete! Redirecting to dashboard...");
      navigate(`/dashboard?farm_id=${selectedFarmId}`);
    } catch (err) {
      const message = getApiErrorMessage(err, "Prediction failed");
      toast.error(message);
      setError(message);
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background" style={{ backgroundImage: "radial-gradient(var(--color-primary) 1px, transparent 1px)", backgroundSize: "24px 24px" }}>
        <div className="flex flex-col items-center gap-lg max-w-md text-center">
          <div className="flex items-center gap-sm mb-md">
            <span className="material-symbols-outlined text-primary text-[32px]">agriculture</span>
            <span className="font-headline-lg text-headline-lg text-primary font-bold">PolliSync</span>
          </div>

          <div className="relative w-40 h-40 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-2 border-outline-variant/20 animate-[spin_4s_linear_infinite]" style={{ borderTopColor: "transparent", borderRightColor: "transparent" }} />
            <div className="absolute inset-2 rounded-full border-4 border-t-primary border-r-transparent border-b-transparent border-l-transparent animate-spin" />
            <div className="relative w-16 h-16 rounded-full bg-surface flex items-center justify-center shadow-sm">
              <span className="material-symbols-outlined text-primary text-[40px] animate-pulse">analytics</span>
            </div>
          </div>

          <p className="font-headline-sm text-headline-sm text-on-surface font-bold transition-all duration-500 h-8">
            {LOADING_MESSAGES[loadMsgIndex]}
          </p>

          <div className="flex gap-[3px] w-64">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="h-1.5 flex-1 rounded-full bg-surface-container-high overflow-hidden"
              >
                <div
                  className="h-full rounded-full bg-primary transition-all duration-700"
                  style={{
                    animation: `pulse-progress 1.5s ease-in-out ${i * 0.25}s infinite`,
                  }}
                />
              </div>
            ))}
          </div>

          <p className="font-body-sm text-body-sm text-on-surface-variant mt-md">
            Compiling multi-variate environmental data. This may take a few moments.
          </p>
        </div>
      </div>
    );
  }

  const selectedFarm = farms.find((f) => f.id === selectedFarmId);
  const selectedDistrict = selectedFarm?.district_slug ? getDistrictBySlug(selectedFarm.district_slug) : null;

  return (
    <div className="mx-auto max-w-[640px] py-8">
      {step === 1 && (
        <>
          <div className="mb-lg">
            <nav className="flex items-center gap-sm text-on-surface-variant font-body-sm text-body-sm mb-md">
              <Link to="/dashboard" className="hover:text-primary transition-colors">Predictions</Link>
              <span className="material-symbols-outlined text-[16px]">chevron_right</span>
              <span className="text-on-surface">New Prediction</span>
            </nav>
            <h1 className="font-headline-lg text-headline-lg text-on-background mb-xs">Select Farm</h1>
            <p className="font-body-md text-body-md text-on-surface-variant">Step 1 of 2: Choose the farm for this pollination forecast.</p>
          </div>

          <div className="mb-xl flex items-center gap-sm">
            <div className="h-2 flex-1 bg-primary rounded-full" />
            <div className="h-2 flex-1 bg-surface-container-high rounded-full" />
          </div>

          {error && (
            <div className="mb-6 rounded-lg bg-error-container p-4 text-body-sm font-medium text-on-error-container">
              {error}
            </div>
          )}

          {loadingFarms ? (
            <div className="text-center py-xl">
              <span className="material-symbols-outlined text-primary text-[48px] animate-spin">progress_activity</span>
              <p className="mt-md text-on-surface-variant">Loading farms...</p>
            </div>
          ) : farms.length === 0 ? (
            <div className="text-center py-xl bg-surface border border-outline-variant rounded-xl">
              <span className="material-symbols-outlined text-on-surface-variant text-[48px]">agriculture</span>
              <p className="mt-md text-on-surface-variant">No farms found. Create a farm first.</p>
              <Link
                to="/farms?new=1"
                className="mt-md inline-flex items-center gap-sm bg-primary text-on-primary px-md py-sm rounded-lg hover:brightness-90 transition-all"
              >
                <span className="material-symbols-outlined text-[18px]">add</span>
                Go to My Farms
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-md">
              {farms.map((farm) => {
                const isSelected = selectedFarmId === farm.id;
                const farmDistrict = farm.district_slug ? getDistrictBySlug(farm.district_slug) : null;
                return (
                  <label key={farm.id} className="relative block cursor-pointer group">
                    <input
                      type="radio"
                      name="farm_selection"
                      className="peer sr-only"
                      checked={isSelected}
                      onChange={() => { setSelectedFarmId(farm.id); selectFarm(farm.id); }}
                    />
                    <div className={`bg-surface rounded-xl p-md flex items-center gap-md transition-all relative overflow-hidden ${
                      isSelected
                        ? "border-2 border-primary shadow-[0_4px_12px_rgba(16,185,129,0.1)]"
                        : "border border-outline-variant shadow-[0_1px_3px_rgba(0,0,0,0.05)] hover:border-primary/50 hover:shadow-[0_4px_12px_rgba(0,0,0,0.05)] group-hover:bg-surface-container-low"
                    }`}>
                      {isSelected && (
                        <div className="absolute right-0 top-0 w-32 h-32 bg-secondary-container/10 rounded-bl-full -mr-8 -mt-8 pointer-events-none" />
                      )}
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 relative z-10 transition-colors ${
                        isSelected
                          ? "bg-secondary-container/20 text-secondary-container"
                          : `${farm.crop_type === "Mustard" ? "bg-secondary-container/20 text-secondary-container" : "bg-surface-container-high text-secondary"}`
                      }`}>
                        <span className="material-symbols-outlined">
                          {CROPS.find((c) => c.value === farm.crop_type)?.icon || "eco"}
                        </span>
                      </div>
                      <div className="flex-1 relative z-10">
                        <h3 className="font-headline-sm text-headline-sm text-on-surface mb-1">{farm.name}</h3>
                        <p className="font-body-sm text-body-sm text-on-surface-variant">
                          {farm.crop_type}
                          {farmDistrict && ` • ${farmDistrict.name}`}
                        </p>
                      </div>
                      {farm.is_default && (
                        <span className="text-body-sm text-primary font-label-sm relative z-10">Default</span>
                      )}
                      <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center relative z-10 transition-colors ${
                        isSelected
                          ? "border-primary bg-primary"
                          : "border-outline-variant group-hover:border-primary/50"
                      }`}>
                        <span className={`material-symbols-outlined text-[16px] font-bold ${
                          isSelected ? "text-white" : "text-transparent"
                        }`}>check</span>
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          )}

          <div className="mt-xl flex justify-between items-center pt-md border-t border-outline-variant">
            <Link to="/dashboard" className="px-md py-2 font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors">
              Cancel
            </Link>
            <button
              onClick={() => { setError(""); setStep(2); }}
              disabled={!selectedFarmId}
              className="bg-primary hover:brightness-90 text-on-primary font-label-md text-label-md py-2 px-xl rounded-lg shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_1px_2px_rgba(0,0,0,0.1)] transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-sm"
            >
              Continue
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            </button>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <button
            onClick={() => setStep(1)}
            className="flex items-center gap-sm text-on-surface-variant hover:text-primary transition-colors font-body-sm mb-lg"
          >
            <span className="material-symbols-outlined text-[18px]">arrow_back</span>
            Back to Farm Selection
          </button>

          <div className="mb-xl">
            <div className="inline-flex items-center gap-xs px-md py-xs rounded-full bg-primary-container/10 text-primary font-label-sm text-label-sm mb-md">
              <span className="material-symbols-outlined text-[16px]">checklist</span>
              Step 2 of 2
            </div>
            <h1 className="font-headline-lg text-headline-lg text-on-background mb-xs">Review & Predict</h1>
            <p className="font-body-md text-body-md text-on-surface-variant">Confirm your farm details before initiating the machine learning analysis.</p>
          </div>

          <div className="mb-xl flex items-center gap-sm">
            <div className="h-2 flex-1 bg-primary rounded-full" />
            <div className="h-2 flex-1 bg-primary rounded-full" />
          </div>

          {error && (
            <div className="mb-6 rounded-lg bg-error-container p-4 text-body-sm font-medium text-on-error-container">
              {error}
            </div>
          )}

          {selectedFarm && (
            <div className="bg-surface border border-outline-variant rounded-xl p-xl shadow-sm relative overflow-hidden">
              <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: "radial-gradient(var(--color-primary) 1px, transparent 1px)", backgroundSize: "20px 20px" }} />
              <div className="relative z-10 space-y-lg">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-md">
                    <span className="material-symbols-outlined text-[24px] text-primary">
                      {CROPS.find((c) => c.value === selectedFarm.crop_type)?.icon || "eco"}
                    </span>
                    <div>
                      <span className="font-label-sm text-label-sm text-on-surface-variant">Farm Name</span>
                      <p className="font-headline-sm text-headline-sm text-on-surface">{selectedFarm.name}</p>
                    </div>
                  </div>
                  <div className="px-md py-xs rounded-full bg-primary-container/10 text-primary font-label-sm text-label-sm flex items-center gap-xs">
                    <span className="material-symbols-outlined text-[16px]">
                      {CROPS.find((c) => c.value === selectedFarm.crop_type)?.icon || "eco"}
                    </span>
                    {selectedFarm.crop_type}
                  </div>
                </div>

                {selectedDistrict && (
                  <div className="flex items-start gap-md pt-md border-t border-outline-variant/50">
                    <span className="material-symbols-outlined text-[24px] text-on-surface-variant">location_on</span>
                    <div>
                      <span className="font-label-sm text-label-sm text-on-surface-variant">Location</span>
                      <p className="font-headline-sm text-headline-sm text-on-surface">{selectedDistrict.name}, {selectedDistrict.state}</p>
                      <p className="font-body-sm font-mono text-on-surface-variant mt-xs">
                        {selectedFarm.location_lat?.toFixed(4)} N, {selectedFarm.location_lng?.toFixed(4)} E
                      </p>
                    </div>
                  </div>
                )}

                {selectedFarm.area_acres && (
                  <div className="pt-md border-t border-outline-variant/50">
                    <div className="flex items-center gap-md">
                      <span className="material-symbols-outlined text-[24px] text-on-surface-variant">square_foot</span>
                      <div>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">Area</span>
                        <p className="font-headline-sm text-headline-sm text-on-surface">{selectedFarm.area_acres} acres</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="mt-lg p-md rounded-lg bg-surface-container-low border border-outline-variant/50 flex items-start gap-md">
            <span className="material-symbols-outlined text-[18px] text-on-surface-variant flex-shrink-0 mt-[2px]">info</span>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              Analysis typically takes 15-30 seconds. This will consume 1 prediction credit from your account.
            </p>
          </div>

          <div className="mt-xl flex justify-between items-center pt-md border-t border-outline-variant">
            <button
              onClick={() => setStep(1)}
              className="px-md py-2 font-label-md text-label-md text-on-surface-variant hover:text-on-surface transition-colors"
            >
              Back
            </button>
            <button
              onClick={handleSubmit}
              className="bg-primary hover:brightness-90 text-on-primary font-label-md text-label-md py-2 px-xl rounded-lg shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_1px_2px_rgba(0,0,0,0.1)] transition-all active:scale-[0.98] flex items-center gap-sm"
            >
              <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
              Predict Pollination
            </button>
          </div>
        </>
      )}
    </div>
  );
}
