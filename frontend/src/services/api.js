import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60000,
});

export async function startTask(payload) {
  const formData = new FormData();

  Object.entries(payload).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    formData.append(key, value);
  });

  const { data } = await api.post("/start-task", formData);
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

export function getDownloadUrl(downloadPath) {
  if (!downloadPath) {
    return "";
  }
  return `${apiBaseUrl}${downloadPath}`;
}
