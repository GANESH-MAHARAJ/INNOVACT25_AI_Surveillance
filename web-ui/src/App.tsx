// src/App.tsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import AlertsTable from "./components/AlertsTable";
import HeatmapPage from "./pages/HeatmapPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-gray-100">
        <header className="border-b border-gray-800">
          <div className="max-w-6xl mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold">
                  HoneyWell AI Surveillance Dashboard
                </h1>
                <p className="text-sm text-gray-400">
                  Multi‑camera monitoring • Evidence clips • Analytics
                </p>
              </div>

              <nav className="flex items-center gap-4 text-sm">
                <NavLink
                  to="/"
                  end
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-md ${
                      isActive
                        ? "bg-gray-800 text-white"
                        : "text-gray-300 hover:text-white hover:bg-gray-900"
                    }`
                  }
                >
                  Events
                </NavLink>
                <NavLink
                  to="/heatmap"
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-md ${
                      isActive
                        ? "bg-gray-800 text-white"
                        : "text-gray-300 hover:text-white hover:bg-gray-900"
                    }`
                  }
                >
                  Heatmaps & Analytics
                </NavLink>
              </nav>
            </div>
          </div>
        </header>

        <main className="max-w-6xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<AlertsTable />} />
            <Route path="/heatmap" element={<HeatmapPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
