import api from "./axios";

export const extractComplaint = async ({ rawText, file } = {}) => {
  const formData = new FormData();

  if (rawText?.trim()) {
    formData.append("raw_text", rawText.trim());
  }

  if (file) {
    formData.append("file", file);
  }

  const response = await api.post("/complaints/extract", formData);

  return response.data;
};