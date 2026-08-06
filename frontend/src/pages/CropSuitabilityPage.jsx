import { useState } from "react";
import Card from "../components/Card";
import { LocationSelector, CROP_LIST } from "../components/ParameterForm";

const CROP_DETAILS = {
  Mustard: {
    icon: "eco",
    scientificName: "Brassica juncea",
    season: "Winter (Oct-Mar)",
    waterNeeds: "Low to medium",
    bloomWindow: "12-15 days",
    pollinator: "Wind & bees",
    idealTemp: "15-25°C",
    soilType: "Well-draining",
    yield: "20-25 quintals/ha",
    idealBees: ["Honeybee", "Bumblebee"],
    challenges: "Temperature fluctuations, frost damage",
    tips: [
      "Sow in October-November for best results",
      "Ensure good drainage to prevent root rot",
      "Monitor for high-temp stress during bloom",
      "Attract native bumblebees for better pollination",
    ],
  },
  Sunflower: {
    icon: "local_florist",
    scientificName: "Helianthus annuus",
    season: "Winter or Summer",
    waterNeeds: "Medium to high",
    bloomWindow: "20-30 days",
    pollinator: "Bees (70%), wind (30%)",
    idealTemp: "18-28°C",
    soilType: "Well-draining",
    yield: "30-35 quintals/ha",
    idealBees: ["Honeybee", "Bumblebee", "Sunflower bee"],
    challenges: "Bee-dependent crop, requires active apiaries",
    tips: [
      "Place bee hives 2-3 weeks before bloom",
      "Avoid pesticides during flowering",
      "Maintain 150m distance from competing crops",
      "Encourage wildflowers around field margins",
    ],
  },
  Cotton: {
    icon: "filter_drama",
    scientificName: "Gossypium",
    season: "Summer (Mar-Jul)",
    waterNeeds: "High",
    bloomWindow: "30-45 days (progressive)",
    pollinator: "Bees (60%), wind (40%)",
    idealTemp: "20-35°C",
    soilType: "Loamy, well-drained",
    yield: "180-200 kg/ha",
    idealBees: ["Honeybee", "Carpenter bee"],
    challenges: "Long bloom window, pest management, heat stress",
    tips: [
      "Place apiaries 4-6 weeks before bloom",
      "Avoid broad-spectrum pesticides during flowering",
      "Intercrop with legumes for enhanced pollinator habitat",
      "Ensure adequate soil moisture, especially during petal drop",
    ],
  },
};

const REGION_CROPS = {
  Nashik: ["Mustard", "Sunflower", "Cotton"],
  Punjab: ["Cotton"],
  Haryana: ["Mustard", "Sunflower"],
  Gujarat: ["Cotton", "Sunflower", "Mustard"],
  "Madhya Pradesh": ["Cotton", "Mustard"],
  Maharashtra: ["Cotton", "Sunflower", "Mustard"],
  Rajasthan: ["Mustard"],
  "Uttar Pradesh": ["Cotton"],
  Karnataka: ["Sunflower", "Cotton"],
  "Andhra Pradesh": ["Cotton"],
  Telangana: ["Cotton", "Sunflower"],
  "Tamil Nadu": ["Sunflower"],
};

export default function CropSuitabilityPage() {
  const [selectedLocation, setSelectedLocation] = useState("");
  const [expandedCrop, setExpandedCrop] = useState(null);

  const recommendedCrops = selectedLocation ? REGION_CROPS[selectedLocation] || [] : [];
  const displayCrops = selectedLocation
    ? CROP_LIST.filter((crop) => recommendedCrops.includes(crop.value))
    : CROP_LIST;

  return (
    <div className="space-y-lg">
      {/* Header */}
      <div>
        <h1 className="font-display text-display text-on-surface">Crop Suitability Guide</h1>
        <p className="font-body-md text-body-md text-on-surface-variant mt-xs">
          Learn about crops suited to your region and season. Information on pollination, blooming
          windows, and best practices.
        </p>
      </div>

      {/* Location Selector */}
      <Card header="Filter by Location" variant="filled">
        <LocationSelector value={selectedLocation} onChange={setSelectedLocation} />
      </Card>

      {/* Info Banner */}
      {selectedLocation && (
        <div className="bg-primary-container/20 border border-primary/30 rounded-lg p-lg">
          <div className="flex gap-md items-start">
            <span className="material-symbols-outlined text-primary text-[28px] flex-shrink-0">
              lightbulb
            </span>
            <div>
              <h3 className="font-headline-sm text-headline-sm text-primary mb-xs">
                {selectedLocation} Recommendations
              </h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                Based on regional climate and soil conditions, these {recommendedCrops.length} crops
                are typically best-suited for {selectedLocation}.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Crop Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-lg">
        {displayCrops.map((crop) => {
          const details = CROP_DETAILS[crop.value];
          const isExpanded = expandedCrop === crop.value;
          const isRecommended = selectedLocation && recommendedCrops.includes(crop.value);

          return (
            <Card
              key={crop.value}
              variant={isRecommended ? "elevated" : "default"}
              className={isRecommended ? "ring-2 ring-primary" : ""}
            >
              <button
                type="button"
                onClick={() => setExpandedCrop(isExpanded ? null : crop.value)}
                className="w-full text-left"
              >
                {/* Header */}
                <div className="flex items-start gap-md mb-md">
                  <div className={`${crop.bg} ${crop.color} p-md rounded-lg flex-shrink-0`}>
                    <span className="material-symbols-outlined text-[28px]">{crop.icon}</span>
                  </div>
                  <div className="flex-1">
                    <div className="flex justify-between items-start gap-md">
                      <div>
                        <h3 className="font-headline-md text-headline-md text-on-surface">
                          {crop.value}
                        </h3>
                        <p className="font-body-sm text-body-sm text-on-surface-variant italic">
                          {details.scientificName}
                        </p>
                      </div>
                      {isRecommended && (
                        <span className="px-sm py-xs bg-primary text-on-primary rounded-full font-label-xs text-label-xs font-bold flex-shrink-0">
                          ⭐ Recommended
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Quick Info Grid */}
                <div className="grid grid-cols-2 gap-md mb-md">
                  <div className="bg-surface-container rounded-lg p-sm">
                    <p className="font-label-xs text-label-xs text-on-surface-variant">Season</p>
                    <p className="font-body-sm text-body-sm text-on-surface mt-xs">
                      {details.season}
                    </p>
                  </div>
                  <div className="bg-surface-container rounded-lg p-sm">
                    <p className="font-label-xs text-label-xs text-on-surface-variant">
                      Pollinator
                    </p>
                    <p className="font-body-sm text-body-sm text-on-surface mt-xs">
                      {details.pollinator}
                    </p>
                  </div>
                  <div className="bg-surface-container rounded-lg p-sm">
                    <p className="font-label-xs text-label-xs text-on-surface-variant">
                      Ideal Temp
                    </p>
                    <p className="font-body-sm text-body-sm text-on-surface mt-xs">
                      {details.idealTemp}
                    </p>
                  </div>
                  <div className="bg-surface-container rounded-lg p-sm">
                    <p className="font-label-xs text-label-xs text-on-surface-variant">
                      Bloom Window
                    </p>
                    <p className="font-body-sm text-body-sm text-on-surface mt-xs">
                      {details.bloomWindow}
                    </p>
                  </div>
                </div>

                {/* Expand Button */}
                <div className="flex items-center gap-xs text-primary font-label-sm text-label-sm font-bold">
                  {isExpanded ? "Show less" : "Show more details"}
                  <span className="material-symbols-outlined text-[20px] transition-transform">
                    {isExpanded ? "expand_less" : "expand_more"}
                  </span>
                </div>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="mt-md pt-md border-t border-outline-variant/50 space-y-md">
                  <div className="grid grid-cols-2 gap-md">
                    <div>
                      <p className="font-label-sm text-label-sm text-on-surface-variant mb-xs">
                        Water Needs
                      </p>
                      <p className="font-body-md text-body-md text-on-surface">{details.waterNeeds}</p>
                    </div>
                    <div>
                      <p className="font-label-sm text-label-sm text-on-surface-variant mb-xs">
                        Soil Type
                      </p>
                      <p className="font-body-md text-body-md text-on-surface">{details.soilType}</p>
                    </div>
                    <div>
                      <p className="font-label-sm text-label-sm text-on-surface-variant mb-xs">
                        Expected Yield
                      </p>
                      <p className="font-body-md text-body-md text-on-surface">{details.yield}</p>
                    </div>
                    <div>
                      <p className="font-label-sm text-label-sm text-on-surface-variant mb-xs">
                        Best Bees
                      </p>
                      <p className="font-body-md text-body-md text-on-surface">
                        {details.idealBees.join(", ")}
                      </p>
                    </div>
                  </div>

                  <div>
                    <h4 className="font-headline-sm text-headline-sm text-on-surface mb-sm">
                      Challenges
                    </h4>
                    <p className="font-body-sm text-body-sm text-on-surface-variant">
                      {details.challenges}
                    </p>
                  </div>

                  <div>
                    <h4 className="font-headline-sm text-headline-sm text-on-surface mb-sm">
                      Best Practices
                    </h4>
                    <ul className="space-y-xs">
                      {details.tips.map((tip, i) => (
                        <li key={i} className="flex gap-sm items-start">
                          <span className="text-primary flex-shrink-0">✓</span>
                          <span className="font-body-sm text-body-sm text-on-surface-variant">
                            {tip}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
