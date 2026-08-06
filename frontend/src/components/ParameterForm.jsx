/**
 * Reusable form components for predictions and farm setup
 * Includes: CropSelector, LocationSelector, FarmSelector
 */
import { useState, useEffect } from "react";
import Select from "./Select";

const CROPS = [
  {
    value: "Mustard",
    icon: "eco",
    desc: "Brassica juncea. High sensitivity to temperature.",
    bg: "bg-secondary-container/20",
    color: "text-secondary-container",
  },
  {
    value: "Sunflower",
    icon: "local_florist",
    desc: "Helianthus annuus. Bee-dependent.",
    bg: "bg-surface-container-high",
    color: "text-secondary",
  },
  {
    value: "Cotton",
    icon: "filter_drama",
    desc: "Gossypium. Complex pollination.",
    bg: "bg-surface-container-high",
    color: "text-on-surface-variant",
  },
];

const LOCATIONS = [
  { name: "Nashik", lat: 19.9975, lng: 73.7898 },
  { name: "Punjab", lat: 30.9, lng: 75.8573 },
  { name: "Haryana", lat: 29.0588, lng: 76.0856 },
  { name: "Gujarat", lat: 23.0225, lng: 72.5714 },
  { name: "Madhya Pradesh", lat: 23.2599, lng: 77.4126 },
  { name: "Maharashtra", lat: 19.7515, lng: 75.7139 },
  { name: "Rajasthan", lat: 27.0238, lng: 74.2179 },
  { name: "Uttar Pradesh", lat: 26.8467, lng: 80.9462 },
  { name: "Karnataka", lat: 15.3173, lng: 75.7139 },
  { name: "Andhra Pradesh", lat: 15.9129, lng: 79.7399 },
  { name: "Telangana", lat: 17.1232, lng: 79.2089 },
  { name: "Tamil Nadu", lat: 11.1271, lng: 78.6569 },
];

export function CropSelector({ value = "", onChange, disabled = false }) {
  return (
    <div className="space-y-sm">
      <label className="block font-label-md text-label-md font-bold text-on-surface">Crop</label>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-md">
        {CROPS.map((crop) => (
          <button
            key={crop.value}
            onClick={() => onChange(crop.value)}
            disabled={disabled}
            className={`p-md rounded-lg border-2 transition ${
              value === crop.value
                ? "border-primary bg-primary-container/20"
                : "border-outline-variant bg-surface hover:border-primary/50"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <div className={`${crop.bg} ${crop.color} w-12 h-12 rounded-lg flex items-center justify-center mb-sm mx-auto`}>
              <span className="material-symbols-outlined">{crop.icon}</span>
            </div>
            <p className="font-label-md text-label-md text-on-surface font-bold">{crop.value}</p>
            <p className="font-body-xs text-body-xs text-on-surface-variant mt-xs">{crop.desc}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

export function LocationSelector({ value = "", onChange, disabled = false }) {
  return (
    <div className="space-y-sm">
      <Select
        label="Location"
        value={value}
        onChange={onChange}
        options={LOCATIONS.map((l) => ({ value: l.name, label: l.name }))}
        placeholder="Select a location"
        disabled={disabled}
      />
      {value && (
        <p className="font-body-xs text-body-xs text-on-surface-variant">
          {LOCATIONS.find((l) => l.name === value)?.name}
        </p>
      )}
    </div>
  );
}

export function FarmSelector({ farms = [], value = "", onChange, disabled = false }) {
  if (farms.length === 0) {
    return null;
  }

  return (
    <div className="space-y-sm">
      <Select
        label="Select Farm"
        value={value}
        onChange={onChange}
        options={farms.map((f) => ({
          value: f.id,
          label: `${f.name} - ${f.crop} (${f.location})`,
        }))}
        placeholder="Choose a farm"
        disabled={disabled}
      />
    </div>
  );
}

export function DateSelector({ value = "", onChange, disabled = false, label = "Date" }) {
  return (
    <div className="space-y-sm">
      <label className="block font-label-md text-label-md font-bold text-on-surface">{label}</label>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="w-full px-md py-sm rounded-lg border border-outline-variant bg-surface text-on-surface font-body-md disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
    </div>
  );
}

export const CROP_LIST = CROPS;
export const LOCATION_LIST = LOCATIONS;
