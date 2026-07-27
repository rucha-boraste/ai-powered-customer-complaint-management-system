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
  },
});

export const {
  setComplaint,
  updateField,
  clearComplaint,
} = complaintSlice.actions;

export default complaintSlice.reducer;