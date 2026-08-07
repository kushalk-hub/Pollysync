import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import ShaderBackground from "../components/ShaderBackground";

const FEATURES = [
  {
    title: "Flowering Forecasts",
    text: "Get hyper-local predictions for exact flowering windows based on weather patterns and crop history.",
    icon: "calendar_month",
  },
  {
    title: "Pollination Score",
    text: "Real-time risk assessment of bee activity and climatic conditions affecting fertilization.",
    icon: "shield",
  },
  {
    title: "AI Recommendations",
    text: "Customized actionable advice on when to intervene and how to protect your sensitive flowering crops.",
    icon: "auto_awesome",
  },
];

const CROPS = [
  { name: "Mustard", emoji: "🌼" },
  { name: "Sunflower", emoji: "🌻" },
  { name: "Cotton", emoji: "☁️" },
];

const REGIONS = ["Mumbai", "Nashik", "Pune", "Solapur", "Nagpur", "Kolhapur", "Amravati", "Satara", "Aurangabad", "Latur"];

export default function HomePage() {
  const { user } = useAuth();
  const { dark, toggle } = useTheme();

  return (
    <div className="bg-background text-on-surface font-body overflow-x-hidden">
      <nav className="bg-surface/80 backdrop-blur-md font-label-md text-label-md w-full sticky top-0 z-50 border-b border-outline-variant/30 shadow-sm">
        <div className="flex justify-between items-center w-full px-6 py-4 max-w-container-max mx-auto">
          <div className="font-headline-sm text-headline-sm font-bold text-primary flex items-center gap-2">
            <span className="material-symbols-outlined text-primary-container filled">eco</span>
            <span>PolliSync</span>
          </div>
          <div className="hidden md:flex items-center gap-xl">
            <a className="text-on-surface-variant hover:text-primary transition-colors" href="#features">Features</a>
            <a className="text-on-surface-variant hover:text-primary transition-colors" href="#crops">Crops</a>
          </div>
          <div className="flex items-center gap-md">
            <button
              onClick={toggle}
              className="p-sm rounded-full text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-all"
              title={dark ? "Switch to light mode" : "Switch to dark mode"}
            >
              <span className="material-symbols-outlined text-xl">{dark ? "light_mode" : "dark_mode"}</span>
            </button>
            {user ? (
              <Link
                to="/dashboard"
                className="px-md py-sm bg-primary text-on-primary rounded-lg font-label-md shadow-md hover:opacity-90 active:scale-95 transition-all"
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-md py-sm border border-outline rounded-lg text-on-surface font-label-md hover:bg-surface-container-low transition-all"
                >
                  Login
                </Link>
                <Link
                  to="/register"
                  className="px-md py-sm bg-primary text-on-primary rounded-lg font-label-md shadow-md hover:opacity-90 active:scale-95 transition-all"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      <section className="relative min-h-[750px] flex flex-col items-center justify-center text-center px-6 overflow-hidden">
        <img
          src="/dashboard.png"
          alt=""
          aria-hidden="true"
          draggable={false}
          className="absolute inset-0 w-full h-full object-cover pointer-events-none"
        />
        <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-background/80 via-background/40 to-background/80" />
        <ShaderBackground variant="light" className="opacity-30" />
        <div className="relative z-10 max-w-4xl mx-auto space-y-lg mt-3xl animate-fade-in-up">
          <h1 className="font-display text-display md:text-[64px] md:leading-[1.1] text-on-surface">
            Know Before Your <br className="hidden md:block" />
            <span className="text-primary">Crops Flower</span>
          </h1>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mx-auto">
            AI-powered pollination forecasts for Indian farmers. Predict flowering windows, bee activity, and weather risks — all in one dashboard.
          </p>
          <div className="flex flex-col md:flex-row items-center justify-center gap-md pt-md">
            {user ? (
              <Link
                to="/dashboard"
                className="px-3xl py-md bg-primary-container text-on-primary-container font-label-md text-lg rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2"
              >
                Go to Dashboard
                <span className="material-symbols-outlined">arrow_forward</span>
              </Link>
            ) : (
              <Link
                to="/register"
                className="px-3xl py-md bg-primary-container text-on-primary-container font-label-md text-lg rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2"
              >
                Start Predicting
                <span className="material-symbols-outlined">arrow_forward</span>
              </Link>
            )}
            <a
              href="https://youtu.be/L-GMdKwa5uE?si=jMtcKcsGeJxxUnfO"
              target="_blank"
              rel="noreferrer"
              className="px-3xl py-md border-2 border-outline/30 text-on-surface font-label-md text-lg rounded-xl hover:bg-surface-container-high transition-all flex items-center gap-2"
            >
              <span className="material-symbols-outlined">play_circle</span>
              Watch Demo
            </a>
          </div>
        </div>

        <div className="mt-3xl w-full max-w-container-max animate-fade-in-up stagger-3">
          <div className="pt-2xl border-t border-outline-variant/30 flex flex-wrap justify-center items-center gap-xl opacity-60 grayscale hover:grayscale-0 transition-all duration-500">
            {REGIONS.map((r) => (
              <div key={r} className="flex flex-col items-center gap-sm">
                <div className="w-12 h-12 bg-surface-container-highest rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined">map</span>
                </div>
                <span className="font-label-sm uppercase tracking-widest">{r}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative py-3xl px-6 bg-surface-container-lowest overflow-hidden" id="features">
        <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{ backgroundImage: "radial-gradient(var(--color-primary) 1px, transparent 1px)", backgroundSize: "24px 24px" }} />
        <div className="relative z-10 max-w-container-max mx-auto">
          <div className="text-center mb-2xl animate-fade-in-up">
            <h2 className="font-headline-lg text-headline-lg text-on-surface">Precision Features</h2>
            <p className="text-on-surface-variant font-body-md mt-sm">Data-driven insights for maximum yield optimization.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-lg">
            {FEATURES.map((f, i) => (
              <div
                key={f.title}
                className={`group p-xl bg-surface border border-outline-variant/30 rounded-xl hover:shadow-xl hover:-translate-y-1 transition-all duration-300 card-hover animate-fade-in-up stagger-${i + 1}`}
              >
                <div className="w-12 h-12 bg-primary/10 text-primary rounded-lg flex items-center justify-center mb-md group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined">{f.icon}</span>
                </div>
                <h3 className="font-headline-sm text-headline-sm mb-sm">{f.title}</h3>
                <p className="font-body-md text-on-surface-variant">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-3xl px-6 bg-surface" id="crops">
        <div className="max-w-container-max mx-auto overflow-hidden">
          <h2 className="font-headline-lg text-headline-lg text-on-surface mb-2xl text-center md:text-left">Supported Crops</h2>
          <div className="flex flex-nowrap md:grid md:grid-cols-3 gap-md overflow-x-auto pb-6">
            {CROPS.map((c, i) => (
              <div
                key={c.name}
                className={`min-w-[200px] bg-surface-container-low p-lg rounded-xl border border-outline-variant/20 flex flex-col items-center text-center group hover:bg-primary-container/10 transition-colors animate-fade-in-up stagger-${i + 1}`}
              >
                <span className="text-4xl mb-md">{c.emoji}</span>
                <span className="font-label-md text-label-md text-on-surface font-medium">{c.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-outline-variant bg-surface py-8 text-center font-body-sm text-body-sm text-on-surface-variant">
        <p>PolliSync &mdash; AI-Based Crop Pollination Suitability System</p>
        <p className="mt-1">Built by 4 SY CSE-AI Students</p>
      </footer>
    </div>
  );
}
