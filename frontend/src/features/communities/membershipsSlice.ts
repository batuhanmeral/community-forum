import { createSlice } from '@reduxjs/toolkit';

interface MembershipsState {
  version: number;
}

const initialState: MembershipsState = { version: 0 };

const membershipsSlice = createSlice({
  name: 'memberships',
  initialState,
  reducers: {
    // Bumped after join, leave or community create so the sidebar list refetches.
    membershipsChanged(state) {
      state.version += 1;
    },
  },
});

export const { membershipsChanged } = membershipsSlice.actions;
export default membershipsSlice.reducer;
