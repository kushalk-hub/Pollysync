import { useState, useRef, useEffect, useCallback } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuth } from "../context/AuthContext";
import { useFarm } from "../context/FarmContext";
import { getDashboardSummary, getWeatherCurrent, getLatestPrediction } from "../lib/api";

const INITIAL_MESSAGES = [
  {
    id: 1,
    role: "assistant",
    content: "Hi there! I'm your PolliSync AI assistant. I can help you understand your farm's pollination conditions, crop health, weather risks, and what steps you can take to improve yield. What would you like to know?",
    timestamp: new Date(Date.now() - 60000).toISOString(),
  },
];

const SUGGESTIONS = [
  "What are optimal pollination conditions?",
  "How is my crop health (NDVI)?",
  "Should I water my crops today?",
  "When is the next flowering window?",
];

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

function getCookie(name) {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  const prefix = `${name}=`;
  const match = cookies.find((cookie) => cookie.startsWith(prefix));
  return match ? decodeURIComponent(match.slice(prefix.length)) : null;
}

function getDemoReply(question, farm) {
  const query = question.toLowerCase();
  const farmName = farm?.name || "your selected farm";
  if (query.includes("water") || query.includes("irrig")) return `Soil Moisture: Root zone should be kept evenly moist this week.\nRainfall Impact: Recent rainfall has left healthy moisture levels.\nRecommendation: Check soil moisture before starting irrigation — overwatering can be as harmful as underwatering.`;
  if (query.includes("ndvi") || query.includes("health")) return `NDVI Reading: 0.78 — up from 0.61 three weeks ago.\nTrend: Solid improvement in crop health.\nWatch Area: Lower-west edge of your field is slightly behind the rest.`;
  if (query.includes("flower") || query.includes("bloom")) return `Flowering Window: Predicted July 19–29.\nConfidence: 91%.\nAction: Place or confirm beehives before the window starts.\nCaution: Avoid spraying during active bee hours.`;
  if (query.includes("pollin") || query.includes("bee")) return `PSI: 82 — favorable conditions.\nBee Activity: 4 different bee species detected.\nPrime Window: Calm mornings between 8–11 AM.`;
  return `Conditions: Looking favorable for pollination at ${farmName}.\nRecommendation: Review the morning weather window and keep pesticide applications outside bee-foraging hours.\nNext Step: What specific aspect would you like to dive deeper into?`;
}

async function fetchFarmData(selectedFarm, user) {
  if (!selectedFarm) return null;
  const farmId = selectedFarm.id;
  if (!farmId) {
    return {
      farmer_name: user?.full_name || "Farmer",
      location: selectedFarm.location_name || selectedFarm.location || "Unknown",
      crop_name: selectedFarm.crop_type || selectedFarm.crop || "Unknown",
      farm_size: selectedFarm.area_acres?.toString() || "N/A",
    };
  }

  const result = {
    farmer_name: user?.full_name || "Farmer",
    location: selectedFarm.location_name || selectedFarm.location || "Unknown",
    crop_name: selectedFarm.crop_type || selectedFarm.crop || "Unknown",
    farm_size: selectedFarm.area_acres?.toString() || "N/A",
    season: "Kharif",
    ndvi_interpretation: "Unknown",
    trend: "Stable",
  };

  try {
    const [summary, weather, prediction] = await Promise.allSettled([
      getDashboardSummary(farmId),
      getWeatherCurrent(farmId),
      getLatestPrediction(farmId),
    ]);

    if (weather.status === "fulfilled" && weather.value) {
      const w = weather.value;
      result.temp_current = String(w.temperature ?? "");
      result.humidity = String(w.humidity ?? "");
      result.rainfall_mm = String(w.rainfall ?? "");
      result.wind_speed = String(w.wind_speed ?? "");
    }

    if (prediction.status === "fulfilled" && prediction.value) {
      const p = prediction.value;
      result.ndvi_value = String(p.ndvi_value ?? "");
      result.flowering_date = p.flowering_start ?? "";
      result.risk_score = String(p.psi_score ?? "");
      result.risk_level = p.risk_level ?? "";
      if (p.weather_summary) {
        const ws = typeof p.weather_summary === "object" ? p.weather_summary : {};
        result.temp_forecast = String(ws.temp_forecast ?? ws.temperature ?? result.temp_current ?? "");
      }
    }

    if (summary.status === "fulfilled" && summary.value) {
      const s = summary.value;
      if (s.latest_prediction) {
        const p = s.latest_prediction;
        result.ndvi_value = String(p.ndvi_value ?? result.ndvi_value);
        result.flowering_date = p.flowering_start ?? result.flowering_date;
        result.risk_score = String(p.psi_score ?? result.risk_score);
        result.risk_level = p.risk_level ?? result.risk_level;
      }
      if (s.current_weather) {
        const w = s.current_weather;
        result.temp_current = String(w.temperature ?? result.temp_current);
        result.humidity = String(w.humidity ?? result.humidity);
        result.rainfall_mm = String(w.rainfall ?? result.rainfall_mm);
        result.wind_speed = String(w.wind_speed ?? result.wind_speed);
      }
    }
  } catch {
    // Best-effort
  }

  return result;
}

function MarkdownLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

export default function ChatPage() {
  const { user } = useAuth();
  const { selectedFarm } = useFarm();
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [farmData, setFarmData] = useState(null);
  const [fetchingFarm, setFetchingFarm] = useState(true);
  const bottomRef = useRef(null);
  const apiBase = import.meta.env.VITE_API_URL;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    setFetchingFarm(true);
    fetchFarmData(selectedFarm, user).then((data) => {
      setFarmData(data);
      setFetchingFarm(false);
    });
  }, [user, selectedFarm]);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    const userMsg = {
      id: Date.now(),
      role: "user",
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      if (USE_MOCK) {
        await new Promise((resolve) => setTimeout(resolve, 650));
        setMessages((prev) => [...prev, { id: Date.now() + 1, role: "assistant", content: getDemoReply(text, selectedFarm), timestamp: new Date().toISOString() }]);
        return;
      }
      const conversation = [...messages, userMsg].map((m) => ({
        role: m.role === "assistant" ? "model" : "user",
        content: m.content,
      }));

      const payload = { messages: conversation };
      if (farmData) {
        payload.farm_data = farmData;
      }

      const csrfToken = getCookie("XSRF-TOKEN");

      const res = await fetch(`${apiBase}/api/agent/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken ? { "X-XSRF-TOKEN": csrfToken } : {}),
        },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const data = await res.json();
      const aiMsg = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.reply || "I'm sorry, I couldn't generate a response.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: err.message === "Failed to fetch"
            ? "I can't reach the server right now. Please make sure the backend is running and try again."
            : `Sorry, I ran into an error: ${err.message}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [messages, loading, farmData, apiBase, selectedFarm]);

  function handleSubmit(e) {
    e.preventDefault();
    sendMessage(input);
  }

  function formatTime(ts) {
    return new Date(ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  }

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] lg:h-[calc(100vh-8rem)] max-w-[800px] mx-auto">
      <div className="mb-lg">
        <h1 className="font-headline-lg text-headline-lg text-on-surface">AI Assistant</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">
          {farmData
            ? `Ask me about ${farmData.crop_name} at ${farmData.location}`
            : "I can help with pollination, weather, crop health, and more."}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto bg-surface border border-outline-variant rounded-xl p-lg space-y-lg mb-md">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-xl px-lg py-md ${msg.role === "user"
                ? "bg-primary text-on-primary"
                : "bg-surface-container-low border border-outline-variant/50 text-on-surface"
              }`}>
              {msg.role === "assistant" && (
                <div className="flex items-center gap-xs mb-xs">
                  <span className="material-symbols-outlined text-primary text-[16px]">smart_toy</span>
                  <span className="font-label-sm text-label-sm text-primary font-medium">AI Assistant</span>
                </div>
              )}
              {msg.role === "assistant" ? (
                <div className="font-body-md text-body-md prose-chat">
                  <Markdown remarkPlugins={[remarkGfm]} components={{ a: MarkdownLink }}>{msg.content}</Markdown>
                </div>
              ) : (
                <p className="font-body-md text-body-md whitespace-pre-wrap">{msg.content}</p>
              )}
              <span className={`font-label-sm text-label-sm block mt-xs ${msg.role === "user" ? "text-on-primary/60 text-right" : "text-on-surface-variant"
                }`}>
                {formatTime(msg.timestamp)}
              </span>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-surface-container-low border border-outline-variant/50 rounded-xl px-lg py-md">
              <div className="flex items-center gap-xs">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="font-body-sm text-body-sm text-on-surface-variant ml-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-sm mb-md">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => sendMessage(s)}
              className="px-md py-xs bg-surface-container-high text-on-surface-variant font-body-sm text-body-sm rounded-full hover:bg-surface-container-highest transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-sm">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask me anything about your farm..."
          disabled={loading}
          className="flex-1 bg-surface border border-outline-variant rounded-lg px-md py-sm font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/50 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-primary text-on-primary px-lg py-sm rounded-lg font-label-md text-label-md hover:brightness-90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-sm"
        >
          <span className="material-symbols-outlined text-[18px]">send</span>
          Ask
        </button>
      </form>
    </div>
  );
}
