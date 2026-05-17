import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import { Nav } from "./components/Nav.jsx";
import { HomePage } from "./pages/HomePage.jsx";
import { AssessmentPage } from "./pages/AssessmentPage.jsx";
import { TrainingPage } from "./pages/TrainingPage.jsx";
import { ReviewPage } from "./pages/ReviewPage.jsx";
import { ROUTES, KEY_BY_PATH } from "./navigation.js";

// Bridges the prototype's onNav(key) API to the router so page components
// stay unchanged from the design source.
export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const onNav = (key) => navigate(ROUTES[key] ?? "/");
  const page = KEY_BY_PATH[location.pathname] ?? "home";

  return (
    <div className="app">
      <Nav page={page} onNav={onNav} />
      <Routes>
        <Route path="/" element={<HomePage onNav={onNav} />} />
        <Route path="/assessment" element={<AssessmentPage onNav={onNav} />} />
        <Route path="/training" element={<TrainingPage onNav={onNav} />} />
        <Route path="/review" element={<ReviewPage onNav={onNav} />} />
        <Route path="*" element={<HomePage onNav={onNav} />} />
      </Routes>
    </div>
  );
}
