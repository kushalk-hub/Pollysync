import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getDashboardSummary } from "../lib/api";
import { useFarm } from "../context/FarmContext";
import BeeMap from "../components/BeeMap";
import FloweringCalendar from "../components/FloweringCalendar";
import NDVICard from "../components/NDVICard";
import NDVITrendChart from "../components/NDVITrendChart";
import PSIgauge from "../components/PSIgauge";
import PollenBar from "../components/PollenBar";
import RecommendationCard from "../components/RecommendationCard";
import WeatherCard from "../components/WeatherCard";
import WeatherTrendChart from "../components/WeatherTrendChart";
import PSIHistoryChart from "../components/PSIHistoryChart";
import { DashboardSkeleton, EmptyState, ErrorState } from "../components/LoadingSkeleton";

const riskStyle = {
  Low: "bg-primary-container/15 text-primary",
  Medium: "bg-secondary-container/20 text-secondary",
  High: "bg-tertiary-container/20 text-tertiary",
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { selectedFarmId, selectedFarm, loadingFarms, selectFarm } = useFarm();
  const requestedFarmId = searchParams.get("farm_id");
  const farmId = requestedFarmId || selectedFarmId;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [trendTab, setTrendTab] = useState("forecast");
  const [showMap, setShowMap] = useState(false);

  useEffect(() => {
    if (requestedFarmId) selectFarm(requestedFarmId);
  }, [requestedFarmId, selectFarm]);

  useEffect(() => {
    if (loadingFarms) return;
    if (!farmId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    getDashboardSummary(farmId)
      .then(setData)
      .catch((err) => setError(err?.response?.data?.detail || err.message || "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, [farmId, loadingFarms]);

  if (loading || loadingFarms) return <DashboardSkeleton />;
  if (error) return <ErrorState error={error} onRetry={() => window.location.reload()} />;
  if (!data) {
    return (
      <EmptyState
        icon="agriculture"
        title="Open a farm workspace"
        description="Add a farm or select an existing farm to unlock your daily field workspace."
        action={() => navigate("/farms?new=1")}
        actionLabel="Go to My Farms"
      />
    );
  }

  const farm = data.farm || selectedFarm || {};
  const weather = data.current_weather || {};
  const prediction = data.latest_prediction || {};
  const risk = prediction.risk_level || "Medium";

  return (
    <div className="space-y-lg pb-lg">
      <header className="flex flex-col gap-md sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-label-sm text-primary font-bold uppercase tracking-wide">Field workspace</p>
          <h1 className="mt-1 font-display text-display text-on-surface">Good {new Date().getHours() < 12 ? "morning" : "day"}, {farm.name || "farmer"}</h1>
          <p className="mt-1 text-body-sm text-on-surface-variant">Updated from your latest prediction</p>
        </div>
        <div className="flex flex-col gap-sm sm:flex-row sm:items-center">
          <button onClick={() => navigate(`/predict?farm_id=${farmId}`)} className="min-h-11 inline-flex items-center justify-center gap-sm rounded-lg bg-primary px-lg text-label-md font-bold text-on-primary shadow-sm hover:brightness-95">
            <span className="material-symbols-outlined">auto_awesome</span>
            Run prediction
          </button>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-lg lg:grid-cols-12">
        <article className="rounded-2xl border border-outline-variant bg-surface p-lg shadow-sm lg:col-span-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-label-sm text-on-surface-variant">Pollination suitability</p>
              <h2 className="mt-1 text-headline-md font-headline-md text-on-surface">Today's field condition</h2>
            </div>
            <span className={`rounded-full px-sm py-xs text-label-sm font-bold ${riskStyle[risk]}`}>{risk} risk</span>
          </div>
          <div className="flex flex-col items-center gap-md sm:flex-row sm:justify-between">
            <PSIgauge score={prediction.psi_score} />
            <div className="flex-1">
              <p className="text-headline-sm font-headline-sm text-on-surface">{risk === "Low" ? "Conditions look favorable" : risk === "High" ? "Take action before peak activity" : "Monitor conditions closely"}</p>
              <p className="mt-sm text-body-md text-on-surface-variant">{prediction.flowering_confidence != null ? `${Math.round(Number(prediction.flowering_confidence) * 100)}% flowering-window confidence.` : "Run a prediction to see the current flowering outlook."}</p>
              <button onClick={() => navigate("/reports")} className="mt-md text-label-md font-bold text-primary">View full performance</button>
            </div>
          </div>
        </article>

        <RecommendationCard text={prediction.recommendation} riskLevel={risk} className="lg:col-span-7" />
      </section>

      {prediction.is_stale && (
        <section className="flex flex-col gap-md rounded-2xl border border-secondary/40 bg-secondary-container/10 p-lg sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-sm">
            <span className="material-symbols-outlined text-secondary">update</span>
            <div>
              <h2 className="font-label-md text-label-md text-on-surface">Farm settings changed</h2>
              <p className="mt-1 text-body-sm text-on-surface-variant">This result uses previous crop, date, or location settings. Run a new prediction for an updated recommendation.</p>
            </div>
          </div>
          <button onClick={() => navigate(`/predict?farm_id=${farmId}`)} className="min-h-11 rounded-lg bg-primary px-lg text-label-md font-bold text-on-primary">Run new prediction</button>
        </section>
      )}

      <section>
        <div className="mb-md">
          <h2 className="text-headline-md font-headline-md text-on-surface">Current microclimate</h2>
          <p className="text-body-sm text-on-surface-variant">Fast weather context for field decisions.</p>
        </div>
        <div className="grid grid-cols-2 gap-sm lg:grid-cols-4">
          <WeatherCard label="Temperature" value={weather.temperature ?? "--"} unit="C" icon="temperature" trend={2} />
          <WeatherCard label="Humidity" value={weather.humidity ?? "--"} unit="%" icon="humidity" trend={-4} />
          <WeatherCard label="Rainfall" value={weather.rainfall ?? "--"} unit="mm" icon="rainfall" />
          <WeatherCard label="Wind" value={weather.wind_speed ?? "--"} unit="km/h" icon="wind" trend={-2} />
        </div>
      </section>

      <section className="grid grid-cols-1 gap-lg lg:grid-cols-2">
        <FloweringCalendar start={prediction.flowering_start} end={prediction.flowering_end} confidence={prediction.flowering_confidence} />
        <PollenBar pollen={prediction.pollen_summary} />
        <NDVICard value={prediction.ndvi_value} onViewTrend={() => setTrendTab("ndvi")} />
      </section>

      <section className="rounded-2xl border border-outline-variant bg-surface p-lg shadow-sm">
        <div className="flex flex-col gap-md sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-headline-md font-headline-md text-on-surface">Trends</h2>
            <p className="text-body-sm text-on-surface-variant">{trendTab === "forecast" ? "Seven-day temperature forecast" : trendTab === "ndvi" ? "Crop-health movement over prediction history" : "How your PSI has changed over time"}</p>
          </div>
          <div role="tablist" aria-label="Trend views" className="inline-flex w-fit rounded-lg bg-surface-container p-1">
            {[["forecast", "Forecast"], ["history", "PSI"], ["ndvi", "NDVI"]].map(([id, label]) => (
              <button key={id} role="tab" aria-selected={trendTab === id} onClick={() => setTrendTab(id)} className={`min-h-11 rounded-md px-md text-label-sm ${trendTab === id ? "bg-surface text-primary shadow-sm font-bold" : "text-on-surface-variant"}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-lg">
          {trendTab === "forecast" ? <WeatherTrendChart farmId={farmId} /> : trendTab === "ndvi" ? <NDVITrendChart farmId={farmId} /> : <PSIHistoryChart farmId={farmId} />}
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-outline-variant bg-surface shadow-sm">
        <button aria-expanded={showMap} onClick={() => setShowMap((value) => !value)} className="flex min-h-14 w-full items-center justify-between px-lg text-left">
          <span>
            <span className="block text-headline-sm font-headline-sm text-on-surface">Field activity</span>
            <span className="text-body-sm text-on-surface-variant">Farm location and recorded bee sightings</span>
          </span>
          <span className="material-symbols-outlined text-primary">{showMap ? "expand_less" : "expand_more"}</span>
        </button>
        {showMap && (
          <div className="border-t border-outline-variant p-md">
            <BeeMap center={[farm.location_lat || 20, farm.location_lng || 78]} farmName={farm.name} crop={farm.crop_type} psiScore={prediction.psi_score} occurrences={(data.occurrences || []).map((o) => ({ species: o.species, lat: o.lat, lng: o.lng }))} />
          </div>
        )}
      </section>
    </div>
  );
}
