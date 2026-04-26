import { useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import { Navigate, Route, Routes } from "react-router-dom";

import { AUTH_STATE_EVENT, TOKEN_STORAGE_KEY } from "./api/fairlensApi";
import ProtectedLayout from "./layouts/ProtectedLayout";
import Audit from "./pages/Audit";
import Candidates from "./pages/Candidates";
import Dashboard from "./pages/Dashboard";
import LoginPage from "./pages/LoginPage";
import Mitigate from "./pages/Mitigate";
import RegisterPage from "./pages/RegisterPage";

const getStoredToken = () =>
  typeof window !== "undefined" ? localStorage.getItem(TOKEN_STORAGE_KEY) : null;

function ProtectedRoutes({ token }) {
  return token ? <ProtectedLayout /> : <Navigate to="/login" replace />;
}

function App() {
  const [token, setToken] = useState(getStoredToken);

  useEffect(() => {
    const syncToken = () => setToken(getStoredToken());
    window.addEventListener("storage", syncToken);
    window.addEventListener(AUTH_STATE_EVENT, syncToken);
    return () => {
      window.removeEventListener("storage", syncToken);
      window.removeEventListener(AUTH_STATE_EVENT, syncToken);
    };
  }, []);

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            borderRadius: "18px",
            background: "#0f172a",
            color: "#ffffff"
          }
        }}
      />
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
        <Route path="/register" element={token ? <Navigate to="/dashboard" replace /> : <RegisterPage />} />
        <Route path="/" element={<Navigate to={token ? "/dashboard" : "/login"} replace />} />
        <Route element={<ProtectedRoutes token={token} />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/candidates/:auditId" element={<Candidates />} />
          <Route path="/mitigate/:auditId" element={<Mitigate />} />
        </Route>
      </Routes>
    </>
  );
}

export default App;
