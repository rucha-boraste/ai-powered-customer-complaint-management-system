import api from "./axios";

export const extractComplaint = async ({ rawText, file, currentComplaint } = {}) => {
  const formData = new FormData();

  if (rawText?.trim()) {
    formData.append("raw_text", rawText.trim());
  }

  if (file) {
    formData.append("file", file);
  }

  if (currentComplaint) {
    formData.append("current_complaint", JSON.stringify(currentComplaint));
  }

  const response = await api.post("/complaints/extract", formData);

  return response.data;
};

export const saveComplaint = async (complaintData = {}) => {
  const optionalFields = new Set([
    "product_strength",
    "batch_number",
    "manufacturing_date",
    "expiry_date",
    "quantity_affected",
    "complaint_date",
    "complaint_description",
    "storage_path",
  ]);

  const { risk_assessment, ...rest } = complaintData;

  const payload = Object.entries(rest).reduce((acc, [key, value]) => {
    if (value === "" && optionalFields.has(key)) {
      acc[key] = null;
    } else {
      acc[key] = value;
    }

    return acc;
  }, {});

  if (risk_assessment?.id) {
    payload.risk_assessment_id = risk_assessment.id;
  }

  const response = await api.post("/complaints/save", payload);

  return response.data;
};

export const assessComplaint = async (complaintData = {}) => {
  const response = await api.post("/complaints/assess", complaintData);

  return response.data;
};