import { createSlice } from "@reduxjs/toolkit";

const initialState = {
  complaint_source: "",
  customer_name: "",
  product_name: "",
  product_strength: "",
  batch_number: "",
  manufacturing_date: "",
  expiry_date: "",
  quantity_affected: "",
  complaint_type: "",
  complaint_date: "",
  complaint_description: "",
  initial_severity: "",
  priority: "",
  storage_path: null,
  risk_assessment: null,
};

const complaintSlice = createSlice({
  name: "complaint",
  initialState,

  reducers: {
    setComplaint(state, action) {
      return { ...state, ...action.payload };
    },

    updateField(state, action) {
      const { field, value } = action.payload;
      state[field] = value;
    },

    clearComplaint() {
      return initialState;
    },
    setRiskAssessment(state, action) {
      state.risk_assessment = action.payload;
    },
    clearRiskAssessment(state) {
      state.risk_assessment = null;
    },
  },
});

export const {
  setComplaint,
  updateField,
  clearComplaint,
  setRiskAssessment,
  clearRiskAssessment,
} = complaintSlice.actions;

export default complaintSlice.reducer;