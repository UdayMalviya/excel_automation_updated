import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

export async function startTask(payload) {
  const { data } = await api.post("/start-task", payload);
  return data;
}

export async function submitCaptcha(payload) {
  const { data } = await api.post("/submit-captcha", payload);
  return data;
}

export async function healthCheck() {
  const { data } = await api.get("/health");
  return data;
}
