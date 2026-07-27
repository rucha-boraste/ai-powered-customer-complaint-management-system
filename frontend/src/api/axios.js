import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 60000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!error.response) {
      const networkMessage =
        error.code === "ERR_NETWORK" || error.message?.includes("Network Error")
          ? "Unable to reach the backend. Please make sure the FastAPI server is running on port 8000."
          : "Unexpected request error.";

      return Promise.reject(new Error(networkMessage));
    }

    return Promise.reject(error);
  }
);

export default api;