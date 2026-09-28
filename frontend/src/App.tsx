import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Evaluation from "./pages/Evaluation";
import NewForecast from "./pages/NewForecast";
import RepPage from "./pages/RepPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="reps" element={<Navigate to="/reps/priya" replace />} />
        <Route path="reps/:repId" element={<RepPage />} />
        <Route path="forecast" element={<NewForecast />} />
        <Route path="evaluation" element={<Evaluation />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
