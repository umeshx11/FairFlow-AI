import axios from "axios";
import toast from "react-hot-toast";

export const TOKEN_STORAGE_KEY = "fairlens_token";
export const USER_EMAIL_STORAGE_KEY = "fairlens_user_email";
export const USER_ID_STORAGE_KEY = "fairlens_user_id";
export const LAST_AUDIT_STORAGE_KEY = "fairlens_last_audit_id";
export const AUTH_STATE_EVENT = "fairlens:auth-state-changed";

const runtimeHost = typeof window !== "undefined" ? window.location.hostname : "localhost";
const apiHost = runtimeHost === "127.0.0.1" ? "127.0.0.1" : "localhost";

const api = axios.create({
  baseURL: `http://${apiHost}:8000`
});

const isAuthRoute = (pathname) => pathname === "/login" || pathname === "/register";

const emitAuthStateChange = () => {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_STATE_EVENT));
  }
};

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const requestUrl = error.config?.url || "";
    const isAuthRequest = requestUrl.includes("/auth/login") || requestUrl.includes("/auth/register");
    if (error.response?.status === 401 && !isAuthRequest) {
      clearSession();
      if (typeof window !== "undefined" && !isAuthRoute(window.location.pathname)) {
        window.location.replace("/login");
      }
    }
    return Promise.reject(error);
  }
);

const getErrorMessage = (error, fallbackMessage) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => item?.msg || item?.message || String(item))
      .filter(Boolean)
      .join(", ");
  }
  if (typeof error?.response?.data === "string" && error.response.data.trim()) {
    return error.response.data;
  }
  return fallbackMessage || "Something went wrong.";
};

const performRequest = async (request, fallbackMessage) => {
  try {
    const response = await request();
    return response.data;
  } catch (error) {
    if (error?.response?.status === 401) {
      throw error;
    }
    toast.error(getErrorMessage(error, fallbackMessage));
    throw error;
  }
};

export const persistSession = (tokenData) => {
  localStorage.setItem(TOKEN_STORAGE_KEY, tokenData.access_token);
  localStorage.setItem(USER_EMAIL_STORAGE_KEY, tokenData.user_email);
  localStorage.setItem(USER_ID_STORAGE_KEY, tokenData.user_id);
  emitAuthStateChange();
};

export const clearSession = () => {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_EMAIL_STORAGE_KEY);
  localStorage.removeItem(USER_ID_STORAGE_KEY);
  localStorage.removeItem(LAST_AUDIT_STORAGE_KEY);
  emitAuthStateChange();
};

export const register = async (data) =>
  performRequest(() => api.post("/auth/register", data), "Registration failed.");

export const login = async (data) =>
  performRequest(() => api.post("/auth/login", data), "Login failed.");

export const uploadAudit = async (formData, config = {}) =>
  performRequest(
    () =>
      api.post("/audit/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data"
        },
        onUploadProgress: config.onUploadProgress
      }),
    "Audit upload failed."
  );

export const uploadMultimodalAudit = async (formData) =>
  performRequest(
    () =>
      api.post("/audit/upload-multimodal", formData, {
        headers: {
          "Content-Type": "multipart/form-data"
        }
      }),
    "Multimodal upload failed."
  );

export const getAudit = async (id) =>
  performRequest(() => api.get(`/audit/${id}`), "Could not load audit.");

export const listAudits = async () =>
  performRequest(() => api.get("/audit/list"), "Could not load audits.");

export const getCandidates = async (auditId, params = {}) =>
  performRequest(
    () => api.get(`/candidates/${auditId}`, { params }),
    "Could not load candidates."
  );

export const explainCandidate = async (id) =>
  performRequest(() => api.get(`/explain/${id}`), "Could not load candidate explanation.");

export const getCounterfactual = async (candidateId) =>
  performRequest(
    () => api.post("/counterfactual", { candidate_id: candidateId }),
    "Could not generate counterfactual."
  );

export const mitigateAudit = async (auditId) =>
  performRequest(() => api.post(`/mitigate/${auditId}`), "Mitigation analysis failed.");

export const runSyntheticPatch = async (auditId, targetAttribute = "gender") =>
  performRequest(
    () => api.post(`/mitigate/synthetic/${auditId}`, null, { params: { target_attribute: targetAttribute } }),
    "Synthetic patch generation failed."
  );

export const runGovernanceAuditor = async (auditId) =>
  performRequest(
    () => api.post(`/governance/auditor/${auditId}`),
    "Could not generate Ethos agent recommendation."
  );

export const runDeepInspection = async (auditId) =>
  performRequest(
    () => api.post(`/inspection/deep/${auditId}`),
    "Could not run deep inspection."
  );

export const downloadReport = async (auditId) => {
  try {
    const response = await api.get(`/report/${auditId}`, {
      responseType: "blob"
    });
    return response.data;
  } catch (error) {
    toast.error(getErrorMessage(error, "Could not download report."));
    throw error;
  }
};

export default api;
